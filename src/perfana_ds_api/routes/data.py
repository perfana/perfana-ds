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

from typing import Annotated

from celery import Task, chain, group
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from perfana_ds.catalog.catalog import get_catalog
from perfana_ds.pipelines.adapt.pipeline import (
    run_adapt_pipeline,
)
from perfana_ds.pipelines.checks.pipeline import run_check_pipeline
from perfana_ds.pipelines.control_groups.pipeline import run_control_groups_pipeline
from perfana_ds.pipelines.metrics.pipeline import (
    run_metrics_pipeline,
    run_reevaluate_pipeline,
)
from perfana_ds.pipelines.panels.pipeline import run_panels_pipeline
from perfana_ds.pipelines.dynatrace.pipeline import batch_process_dynatrace_dashboards, process_dynatrace_queries_from_collection
from perfana_ds.pipelines.statistics.pipeline import run_metric_statistics_pipeline
from perfana_ds_api.worker import worker

router = APIRouter()


class TaskResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    taskId: str | None


@worker.task(bind=True, name="Panels")
def update_panels_task(self: Task, testRunId: str):
    run_panels_pipeline(test_run_id=testRunId)
    return True


@router.post("/panels/{testRunId}")
def update_panels(testRunId: str) -> TaskResponse:
    task = update_panels_task.delay(testRunId=testRunId)
    return TaskResponse(taskId=task.id)


@worker.task(bind=True, name="Dynatrace")
def update_dynatrace_task(self: Task, testRunId: str):
    import asyncio
    import logging
    from perfana_ds.catalog.catalog import get_catalog
    from perfana_ds.project_settings import get_settings
    
    logger = logging.getLogger(__name__)
    logger.info(f"🔷 Starting Dynatrace pipeline for test run: {testRunId}")
    
    catalog = get_catalog()
    settings = get_settings()
    
    # Get test run
    logger.info(f"🔷 Loading test run from catalog...")
    test_run = catalog.testRuns.load_object({"testRunId": testRunId})
    if test_run is None:
        logger.error(f"❌ Test run {testRunId} not found")
        raise FileNotFoundError(f"Test run {testRunId} not found")
    
    logger.info(f"✅ Test run loaded: {test_run.testRunId} ({test_run.start} to {test_run.end})")
    
    # Use collection-based approach instead of filesystem dashboards
    logger.info(f"🔷 Processing Dynatrace queries from dynatraceDql collection...")
    logger.info(f"🔍 Filtering for: application={test_run.application}, testEnvironment={test_run.testEnvironment}")
    
    if settings.DYNATRACE_URL:
        logger.info(f"🔷 Processing Dynatrace queries with URL: {settings.DYNATRACE_URL}")
        logger.info(f"🔑 Using API token: {settings.DYNATRACE_API_TOKEN[:20]}..." if settings.DYNATRACE_API_TOKEN else "No API token")
        
        try:
            panel_documents, metrics_documents = asyncio.run(process_dynatrace_queries_from_collection(
                test_run=test_run,
                dynatrace_url=settings.DYNATRACE_URL,
                dynatrace_collection=catalog.dynatrace.collection,
            ))
            
            logger.info(f"📝 Generated {len(panel_documents)} panel documents and {len(metrics_documents)} metrics documents")
            
            # Save panel documents
            logger.info(f"🔷 Saving panel documents to MongoDB...")
            delete_result = catalog.ds.panels.collection.delete_many({"testRunId": testRunId, "datasourceType": "dynatrace"})
            logger.info(f"🗑️ Deleted {delete_result.deleted_count} existing Dynatrace panel documents")
            
            catalog.ds.panels.save_objects(panel_documents)
            logger.info(f"✅ Saved {len(panel_documents)} Dynatrace panel documents")
            
            # Save metrics documents
            if metrics_documents:
                logger.info(f"🔷 Saving metrics documents to MongoDB...")
                delete_metrics_result = catalog.ds.metrics.collection.delete_many({"testRunId": testRunId, "applicationDashboardId": "dynatrace"})
                logger.info(f"🗑️ Deleted {delete_metrics_result.deleted_count} existing Dynatrace metrics documents")
                
                catalog.ds.metrics.save_objects(metrics_documents)
                logger.info(f"✅ Saved {len(metrics_documents)} Dynatrace metrics documents")
                
                # Generate statistics for the saved metrics
                logger.info(f"🔷 Generating metric statistics...")
                run_metric_statistics_pipeline(test_run_ids=[testRunId])
                logger.info(f"✅ Generated metric statistics for test run: {testRunId}")
            
        except Exception as e:
            logger.error(f"❌ Error processing Dynatrace dashboards: {e}")
            raise
            
    else:
        logger.warning("⚠️ DYNATRACE_URL not configured - skipping Dynatrace processing")
    
    logger.info(f"✅ Dynatrace pipeline completed for test run: {testRunId}")
    return True


@router.post("/dynatrace/{testRunId}")
def update_dynatrace(testRunId: str) -> TaskResponse:
    task = update_dynatrace_task.delay(testRunId=testRunId)
    return TaskResponse(taskId=task.id)


@worker.task(bind=True, name="Statistics")
def update_statistics_task(self, test_run_ids: list[str]):
    _ = run_metric_statistics_pipeline(test_run_ids=test_run_ids)
    return True


@worker.task(bind=True, name="Metrics", queue="metrics")
def update_metrics_task(
    self,
    testRunId: str,
    updatePanels: bool = True,
    benchmarksOnly: bool = False,
):
    if updatePanels is True:
        run_panels_pipeline(test_run_id=testRunId)

    run_metrics_pipeline(test_run_id=testRunId, benchmarks_only=benchmarksOnly)
    run_metric_statistics_pipeline(test_run_ids=[testRunId])
    return True


@router.post("/metrics/{testRunId}")
def update_metrics(
    testRunId: str,
    updatePanels: Annotated[bool, Query()] = True,
    benchmarksOnly: Annotated[bool, Query()] = False,
):
    task = update_metrics_task.delay(testRunId, updatePanels, benchmarksOnly)
    return TaskResponse(taskId=task.id)


@router.post("/statistics/{testRunId}")
def update_statistics(testRunId: str) -> TaskResponse:
    task = update_statistics_task.delay(test_run_ids=[testRunId])
    return TaskResponse(taskId=task.id)


@router.post("/batch/statistics/")
def update_statistics_batch(test_run_ids: list[str]) -> TaskResponse:
    task = update_statistics_task.delay(test_run_ids=test_run_ids)
    return TaskResponse(taskId=task.id)


@worker.task(bind=True, name="Control group")
def update_control_group_task(self, test_run_ids: list[str]) -> bool:
    run_control_groups_pipeline(test_run_ids=test_run_ids)
    return True


@router.post("/controlGroup/{testRunId}")
def update_control_group(testRunId: str) -> TaskResponse:
    task = update_control_group_task.delay(test_run_ids=[testRunId])
    return TaskResponse(taskId=task.id)


@worker.task(bind=True, name="Adapt")
def update_adapt_task(
    self,
    test_run_ids: [str],
    updateControlGroup: bool = True,
    updateControlStatistics: bool = True,
    updateResults: bool = True,
    updateConclusion: bool = True,
    updateTrackedResults: bool = True,
) -> bool:
    run_adapt_pipeline(
        test_run_ids=test_run_ids,
        create_control_group=updateControlGroup,
        calculate_statistics=updateControlStatistics,
        evaluate_results=updateResults,
        create_conclusion=updateConclusion,
        reevaluate_tracked_results=updateTrackedResults,
    )
    return True


@router.post("/adapt/{testRunId}")
def update_adapt(
    testRunId: str,
    updateControlGroup: Annotated[bool, Query()] = True,
    updateControlStatistics: Annotated[bool, Query()] = True,
    updateTrackedResults: Annotated[bool, Query()] = True,
) -> TaskResponse:
    task = update_adapt_task.delay(
        test_run_ids=[testRunId],
        updateControlGroup=updateControlGroup,
        updateControlStatistics=updateControlStatistics,
        updateTrackedResults=updateTrackedResults,
    )
    return TaskResponse(taskId=task.id)


@worker.task(bind=True, name="Analyze test", queue="metrics")
def analyze_test_task(self, testRunId: str, adapt: bool = True) -> bool:
    import logging
    logger = logging.getLogger(__name__)
    
    # Run Dynatrace pipeline first to collect data
    logger.info(f"🔷 Starting comprehensive analysis for test run: {testRunId}")
    logger.info(f"🔷 Step 1: Running Dynatrace data collection...")
    update_dynatrace_task(testRunId)
    
    logger.info(f"🔷 Step 2: Running panels pipeline...")
    run_panels_pipeline(test_run_id=testRunId)
    logger.info(f"🔷 Step 3: Running metrics pipeline...")
    run_metrics_pipeline(test_run_id=testRunId)
    logger.info(f"🔷 Step 4: Running statistics pipeline...")
    run_metric_statistics_pipeline(test_run_ids=[testRunId])

    # Run checks pipeline (this includes benchmark comparisons)
    logger.info(f"🔷 Step 5: Running checks pipeline...")
    try:
        run_check_pipeline(test_run_ids=[testRunId])
    except Exception as e:
        # Log error but don't fail the entire task
        logger.error(f"❌ Check pipeline failed for {testRunId}: {e}")

    if adapt is True:
        logger.info(f"🔷 Step 6: Running ADAPT pipeline...")
        run_adapt_pipeline(test_run_ids=[testRunId])
    
    logger.info(f"✅ Comprehensive analysis completed for test run: {testRunId}")
    return True


@router.post("/analyzeTest/{testRunId}")
def analyze_test(
    testRunId: str, adapt: Annotated[bool, Query()] = True
) -> TaskResponse:
    task = analyze_test_task.delay(testRunId, adapt)
    return TaskResponse(taskId=task.id)


@router.post("/refreshAll/{testRunId}")
def refresh_all(testRunId: str, adapt: Annotated[bool, Query()] = True) -> TaskResponse:
    return analyze_test(testRunId, adapt=adapt)


@worker.task(bind=True, name="Reevaluate metrics", queue="metrics")
def reevaluate_checks_task(self, test_run_id: str):
    import logging
    logger = logging.getLogger(__name__)
    
    # Run Dynatrace pipeline first to collect fresh data
    logger.info(f"🔷 Starting reevaluation for test run: {test_run_id}")
    logger.info(f"🔷 Step 1: Running Dynatrace data collection...")
    update_dynatrace_task(test_run_id)
    
    logger.info(f"🔷 Step 2: Running reevaluate pipeline...")
    run_reevaluate_pipeline(test_run_id=test_run_id)

    # Run checks pipeline to generate/update check results and comparisons
    logger.info(f"🔷 Step 3: Running checks pipeline...")
    try:
        run_check_pipeline(test_run_ids=[test_run_id])
    except Exception as e:
        # Log error but don't fail the entire task
        logger.error(f"❌ Check pipeline failed for {test_run_id}: {e}")

    logger.info(f"✅ Reevaluation completed for test run: {test_run_id}")
    return True


@router.post("/reevaluate/checks/{testRunId}")
async def reevaluate_checks(testRunId: str) -> TaskResponse:
    """Re-evaluate checks for given test run id without refreshing the data.

    - update benchmark ids of all metrics, to trigger perfana-check
    - re-evaluate ADAPT results and conclusion
    """
    task = reevaluate_checks_task.delay(test_run_id=testRunId)
    return TaskResponse(taskId=task.id)


@router.post("/reevaluate/adapt/{testRunId}")
async def reevaluate_adapt(
    testRunId: str, updateControlGroup: Annotated[bool, Query()] = True
) -> TaskResponse:
    """Re-evaluate ADAPT compare results and conclusion. Optionally, re-build input."""
    return update_adapt(testRunId=testRunId, updateControlGroup=updateControlGroup)


@router.post("/reevaluate/batch")
async def reevaluate_batch(
    testRunIds: list[str],
    checks: Annotated[bool, Query()] = True,
    adapt: Annotated[bool, Query()] = True,
) -> TaskResponse:
    """Re-evaluate a batch of test runs."""
    # look up test runs and sort by start datetimes
    catalog = get_catalog()
    test_runs = catalog.testRuns.load_objects({"testRunId": {"$in": testRunIds}})
    testRunIds = [test_run.testRunId for test_run in test_runs]
    if len(testRunIds) == 0:
        raise HTTPException(
            status_code=404, detail=f"No existing test runs found in {testRunIds}"
        )
    checks_task_group = group(
        [reevaluate_checks_task.si(test_run_id=testRunId) for testRunId in testRunIds]
    )

    adapt_task_sig = update_adapt_task.si(test_run_ids=testRunIds)
    chain_tasks = []
    if checks is True:
        chain_tasks.append(checks_task_group)

    if adapt is True:
        chain_tasks.append(adapt_task_sig)

    if len(chain_tasks) == 0:
        return TaskResponse(taskId=None, tasks=None, status="SKIPPED")

    task_chord = chain(chain_tasks)
    task = task_chord.delay()
    return TaskResponse(taskId=task.id, tasks=str(task_chord))


MAX_BATCH_SIZE = 100


@router.post("/refresh/batch")
def refresh_batch(
    testRunIds: list[str], adapt: Annotated[bool, Query()] = True
) -> TaskResponse:
    # Deduplicate and limit batch size
    testRunIds = list(set(testRunIds))[:MAX_BATCH_SIZE]
    if len(testRunIds) == 0:
        raise HTTPException(status_code=400, detail="No test run IDs provided")

    metric_tasks = [
        analyze_test_task.si(testRunId=test_run_id, adapt=False)
        for test_run_id in testRunIds
    ]

    if adapt is True:
        adapt_task = update_adapt_task.si(test_run_ids=testRunIds)
        task_chord = chain([group(metric_tasks), adapt_task])
    else:
        task_chord = group(metric_tasks)
    task = task_chord.delay()
    return TaskResponse(taskId=task.id, tasks=str(task_chord))
