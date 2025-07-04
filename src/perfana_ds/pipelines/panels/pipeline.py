# Copyright 2025 Perfana Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from time import time

from celery.utils.log import get_task_logger
from pymongo.errors import PyMongoError

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.pipelines.panels.nodes import create_panel_documents
from perfana_ds.pipelines.panels.perfana_data import (
    PerfanaData,
    get_application_dashboards_for_test_run,
    get_benchmarks_for_test_run,
    get_grafana_dashboards_for_application_dashboards,
)
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def run_panels_pipeline(test_run_id: str, include_dynatrace: bool = True):
    """Run pipeline to build and store grafana dashboard panels."""
    logger.info(f"Create panel documents to test run {test_run_id}")
    start_time = time()

    try:
        catalog = get_catalog()
        test_run: TestRun = catalog.testRuns.load_object({"testRunId": test_run_id})
        if test_run is None:
            raise FileNotFoundError(
                f"Test run {test_run_id} not found in {catalog.testRuns.collection_name}"
            )

        logger.info("Finding application dashboards")
        application_dashboards = get_application_dashboards_for_test_run(
            test_run=test_run,
            application_dashboards_collection=catalog.applicationDashboards.collection,
        )

        logger.info("Finding grafana dashboards")
        grafana_dashboards = get_grafana_dashboards_for_application_dashboards(
            application_dashboards=application_dashboards,
            grafana_dashboards_collection=catalog.grafanaDashboards.collection,
        )

        logger.info("Finding benchmarks")
        benchmarks = get_benchmarks_for_test_run(
            test_run=test_run, benchmarks_collection=catalog.benchmarks.collection
        )

        perfana_data = PerfanaData(
            test_run_id=test_run_id,
            test_run=test_run,
            application_dashboards=application_dashboards,
            benchmarks=benchmarks,
            dashboards=grafana_dashboards,
        )

        logger.info("Create panel documents")
        panel_documents = create_panel_documents(
            perfana_data=perfana_data, grafanas_collection=catalog.grafanas.collection
        )

        logger.info("Saving panel documents")
        try:
            delete_result = catalog.ds.panels.collection.delete_many(
                {"testRunId": test_run_id}
            )
            logger.info(
                f"Deleted {delete_result.deleted_count} existing panel documents"
            )
            catalog.ds.panels.save_objects(panel_documents)
        except PyMongoError as e:
            logger.error(f"Database error while saving panel documents: {str(e)}")
            raise

        # Process Dynatrace dashboards if enabled
        if include_dynatrace:
            logger.info("Processing Dynatrace dashboards")
            try:
                import asyncio
                from perfana_ds.pipelines.dynatrace.pipeline import batch_process_dynatrace_dashboards
                from perfana_ds.project_settings import get_settings
                
                settings = get_settings()
                
                # Get Dynatrace dashboards from filesystem
                dynatrace_dashboards = []
                try:
                    import json
                    import os
                    dashboards_dir = "/Users/daniel/workspace/perfana-ds-fastapi/src/tests/dynatrace-dashboards"
                    if os.path.exists(dashboards_dir):
                        for filename in os.listdir(dashboards_dir):
                            if filename.endswith('.json'):
                                file_path = os.path.join(dashboards_dir, filename)
                                with open(file_path, 'r') as f:
                                    dashboard_json = json.load(f)
                                    dashboard_id = filename.replace('.json', '')
                                    dynatrace_dashboards.append((dashboard_json, dashboard_id))
                except Exception as e:
                    logger.warning(f"Could not load Dynatrace dashboards from filesystem: {e}")
                
                if dynatrace_dashboards and settings.DYNATRACE_URL:
                    dynatrace_panel_documents = asyncio.run(batch_process_dynatrace_dashboards(
                        dashboards=dynatrace_dashboards,
                        test_run=test_run,
                        dynatrace_url=settings.DYNATRACE_URL,
                        dynatrace_collection=catalog.dynatrace.collection,
                    ))
                    
                    # Save Dynatrace panel documents
                    if dynatrace_panel_documents:
                        catalog.ds.panels.save_objects(dynatrace_panel_documents)
                        logger.info(f"Saved {len(dynatrace_panel_documents)} Dynatrace panel documents")
                        panel_documents.extend(dynatrace_panel_documents)
                elif dynatrace_dashboards and not settings.DYNATRACE_URL:
                    logger.warning("Dynatrace dashboards found but DYNATRACE_URL not configured")
                else:
                    logger.info("No Dynatrace dashboards found")
                    
            except Exception as e:
                logger.error(f"Error processing Dynatrace dashboards: {str(e)}")
                # Don't fail the entire pipeline if Dynatrace processing fails

        logger.info(f"Finished in {(time() - start_time):.2f} seconds")
        return panel_documents

    except PyMongoError as e:
        logger.error(f"Database error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        raise
