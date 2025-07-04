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

from typing import Any, List, Tuple
import asyncio
import logging

from perfana_ds.schemas.dynatrace.dashboard import Dashboard
from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
from perfana_ds.schemas.perfana.test_runs import TestRun
from perfana_ds.common.dynatrace_api_auth import get_dynatrace_api_token_from_mongo
from perfana_ds.pipelines.dynatrace.query_constructor import construct_dynatrace_queries_from_dashboard, construct_dynatrace_queries_from_collection
from perfana_ds.pipelines.dynatrace.api_client import query_dynatrace_dashboard_data
from perfana_ds.pipelines.dynatrace.data_processor import process_dynatrace_response_data

logger = logging.getLogger(__name__)


async def process_dynatrace_dashboard(
    dashboard: Dashboard,
    dashboard_id: str,
    test_run: TestRun,
    dynatrace_url: str,
    dynatrace_collection,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Tuple[List[PanelDocument], List[PanelMetricsDocument]]:
    """
    Main pipeline to process a Dynatrace dashboard and return panel documents.
    """
    logger.info(f"🔸 Processing Dynatrace dashboard: {dashboard_id}")
    
    # Get API tokens
    logger.debug(f"🔸 Getting API tokens from environment...")
    from perfana_ds.project_settings import get_settings
    settings = get_settings()
    api_token = settings.DYNATRACE_API_TOKEN
    platform_token = settings.DYNATRACE_PLATFORM_TOKEN
    
    if not api_token:
        logger.warning(f"⚠️ No Dynatrace API token found, trying MongoDB...")
        try:
            api_token = get_dynatrace_api_token_from_mongo(dynatrace_collection)
        except Exception as e:
            logger.warning(f"⚠️ Could not get API token from MongoDB: {e}")
            logger.info(f"🔸 Continuing with platform token only (DQL queries only)")
            api_token = None
    
    logger.info(f"🔑 Using API token: {api_token[:20]}..." if api_token else "❌ No API token available")
    logger.info(f"🔑 Using platform token: {platform_token[:20]}..." if platform_token else "❌ No platform token available")
    
    # Construct queries from dashboard
    logger.info(f"🔸 Constructing queries from dashboard tiles...")
    queries = construct_dynatrace_queries_from_dashboard(dashboard, test_run)
    
    logger.info(f"📋 Generated {len(queries)} queries from dashboard")
    for i, query in enumerate(queries):
        logger.debug(f"Query {i+1}: tile_id={query['tile_id']}, title='{query['tile_title']}'")
        logger.debug(f"  Query: {query['query'][:100]}...")
    
    if not queries:
        logger.warning(f"⚠️ No queries generated from dashboard {dashboard_id}")
        return []
    
    # Execute queries
    logger.info(f"🔸 Executing {len(queries)} queries against Dynatrace API...")
    query_results = await query_dynatrace_dashboard_data(
        queries,
        dynatrace_url,
        api_token,
        platform_token,
        batch_size=batch_size,
        max_concurrent=max_concurrent
    )
    
    logger.info(f"📊 Received {len(query_results)} query results")
    
    # Process results into panel and metrics documents
    logger.info(f"🔸 Processing query results into panel and metrics documents...")
    panel_documents, metrics_documents = process_dynatrace_response_data(
        query_results,
        dashboard_id,
        test_run.testRunId,
        test_run.end.isoformat()
    )
    
    logger.info(f"✅ Generated {len(panel_documents)} panel documents and {len(metrics_documents)} metrics documents from dashboard {dashboard_id}")
    return panel_documents, metrics_documents


async def process_dynatrace_queries_from_collection(
    test_run: TestRun,
    dynatrace_url: str,
    dynatrace_collection,
    dashboard_uid: str = None,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Tuple[List[PanelDocument], List[PanelMetricsDocument]]:
    """
    Main pipeline to process Dynatrace queries from dynatraceDql collection.
    This is the new collection-based approach that doesn't require dashboard JSON files.
    """
    # Extract application and testEnvironment from TestRun for consistency
    application = test_run.application
    test_environment = test_run.testEnvironment
    
    logger.info(f"🔸 Processing Dynatrace queries from collection for {application}.{test_environment}")
    logger.debug(f"🔸 Using TestRun: {test_run.testRunId}")
    
    # Get API tokens
    logger.debug(f"🔸 Getting API tokens from environment...")
    from perfana_ds.project_settings import get_settings
    settings = get_settings()
    api_token = settings.DYNATRACE_API_TOKEN
    platform_token = settings.DYNATRACE_PLATFORM_TOKEN
    
    if not api_token:
        logger.warning(f"⚠️ No Dynatrace API token found, trying MongoDB...")
        try:
            api_token = get_dynatrace_api_token_from_mongo(dynatrace_collection)
        except Exception as e:
            logger.warning(f"⚠️ Could not get API token from MongoDB: {e}")
            logger.info(f"🔸 Continuing with platform token only (DQL queries only)")
            api_token = None
    
    logger.info(f"🔑 Using API token: {api_token[:20]}..." if api_token else "❌ No API token available")
    logger.info(f"🔑 Using platform token: {platform_token[:20]}..." if platform_token else "❌ No platform token available")
    
    # Construct queries from collection
    logger.info(f"🔸 Constructing queries from dynatraceDql collection...")
    queries = construct_dynatrace_queries_from_collection(
        test_run=test_run, 
        dashboard_uid=dashboard_uid
    )
    
    logger.info(f"📋 Generated {len(queries)} queries from collection")
    for i, query in enumerate(queries):
        logger.debug(f"Query {i+1}: tile_id={query['tile_id']}, title='{query['tile_title']}'")
        logger.debug(f"  Dashboard: {query['dashboard_label']}")
        logger.debug(f"  Query: {query['query'][:100]}...")
    
    if not queries:
        logger.warning(f"⚠️ No queries found in collection for {application}.{test_environment}")
        return [], []
    
    # Execute queries
    logger.info(f"🔸 Executing {len(queries)} queries against Dynatrace API...")
    query_results = await query_dynatrace_dashboard_data(
        queries,
        dynatrace_url,
        api_token,
        platform_token,
        batch_size=batch_size,
        max_concurrent=max_concurrent
    )
    
    logger.info(f"📊 Received {len(query_results)} query results")
    
    # Process results into panel and metrics documents
    logger.info(f"🔸 Processing query results into panel and metrics documents...")
    panel_documents, metrics_documents = process_dynatrace_response_data(
        query_results,
        f"{application}-{test_environment}",  # Use app-env as dashboard_id
        test_run.testRunId,
        test_run.end.isoformat()
    )
    
    logger.info(f"✅ Generated {len(panel_documents)} panel documents and {len(metrics_documents)} metrics documents from collection")
    return panel_documents, metrics_documents


def parse_dynatrace_dashboard_json(dashboard_json: dict) -> Dashboard:
    """
    Parse Dynatrace dashboard JSON into Dashboard object.
    """
    return Dashboard(**dashboard_json)


async def batch_process_dynatrace_dashboards(
    dashboards: List[tuple[dict, str]],  # (dashboard_json, dashboard_id)
    test_run: TestRun,
    dynatrace_url: str,
    dynatrace_collection,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> Tuple[List[PanelDocument], List[PanelMetricsDocument]]:
    """
    Process multiple Dynatrace dashboards in parallel.
    """
    logger.info(f"🔸 Starting batch processing of {len(dashboards)} Dynatrace dashboards")
    all_panel_documents = []
    all_metrics_documents = []
    
    async def process_single_dashboard(dashboard_data: tuple[dict, str]) -> Tuple[List[PanelDocument], List[PanelMetricsDocument]]:
        dashboard_json, dashboard_id = dashboard_data
        logger.info(f"🔸 Processing dashboard: {dashboard_id}")
        try:
            logger.debug(f"🔸 Parsing dashboard JSON for {dashboard_id}")
            dashboard = parse_dynatrace_dashboard_json(dashboard_json)
            logger.info(f"✅ Successfully parsed dashboard {dashboard_id}")
            
            panel_docs, metrics_docs = await process_dynatrace_dashboard(
                dashboard,
                dashboard_id,
                test_run,
                dynatrace_url,
                dynatrace_collection,
                batch_size,
                max_concurrent
            )
            logger.info(f"✅ Dashboard {dashboard_id} generated {len(panel_docs)} panel documents and {len(metrics_docs)} metrics documents")
            return panel_docs, metrics_docs
        except Exception as e:
            logger.error(f"❌ Error processing dashboard {dashboard_id}: {e}")
            logger.exception("Full error details:")
            return [], []
    
    # Process dashboards concurrently
    logger.info(f"🔸 Processing dashboards with max concurrency: {max_concurrent}")
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_process(dashboard_data: tuple[dict, str]) -> Tuple[List[PanelDocument], List[PanelMetricsDocument]]:
        async with semaphore:
            return await process_single_dashboard(dashboard_data)
    
    tasks = [limited_process(dashboard_data) for dashboard_data in dashboards]
    logger.info(f"🔸 Created {len(tasks)} processing tasks")
    
    results = await asyncio.gather(*tasks)
    logger.info(f"📊 Completed batch processing, got {len(results)} result sets")
    
    # Flatten results
    for i, (panel_docs, metrics_docs) in enumerate(results):
        logger.debug(f"Result set {i+1}: {len(panel_docs)} panel documents, {len(metrics_docs)} metrics documents")
        all_panel_documents.extend(panel_docs)
        all_metrics_documents.extend(metrics_docs)
    
    logger.info(f"✅ Batch processing complete: {len(all_panel_documents)} total panel documents, {len(all_metrics_documents)} total metrics documents")
    return all_panel_documents, all_metrics_documents