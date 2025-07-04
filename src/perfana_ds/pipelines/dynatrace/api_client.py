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

import asyncio
import logging
import httpx
import os
from typing import Any, Dict, List
from urllib.parse import urljoin

from perfana_ds.common.dynatrace_api_auth import create_dynatrace_api_headers
from perfana_ds.pipelines.dynatrace.query_constructor import (
    construct_dynatrace_api_url,
    prepare_dynatrace_query_payload
)

logger = logging.getLogger(__name__)


class DynatraceAPIClient:
    def __init__(self, base_url: str, api_token: str, platform_token: str = None):
        self.base_url = base_url
        self.api_token = api_token
        self.platform_token = platform_token or os.getenv('DYNATRACE_PLATFORM_TOKEN')
    
    async def execute_query(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute a single Dynatrace query.
        """
        url = construct_dynatrace_api_url(self.base_url, query)
        
        # For DQL queries, add default timeframe parameters
        if 'timeseries' in query.lower() or '|' in query:
            # Extract timeframe from query if present
            import re
            from_match = re.search(r'from:\s*"([^"]+)"', query)
            to_match = re.search(r'to:\s*"([^"]+)"', query)
            
            if from_match:
                kwargs["defaultTimeframeStart"] = from_match.group(1)
            if to_match:
                kwargs["defaultTimeframeEnd"] = to_match.group(1)
        
        payload = prepare_dynatrace_query_payload(query, **kwargs)
        
        # Determine if this is a DQL query and choose appropriate auth
        is_dql_query = 'timeseries' in query.lower() or '|' in query
        
        if is_dql_query:
            if not self.platform_token:
                raise ValueError("DYNATRACE_PLATFORM_TOKEN environment variable is required for DQL queries")
            headers = create_dynatrace_api_headers(self.platform_token, use_bearer=True)
        else:
            headers = create_dynatrace_api_headers(self.api_token, use_bearer=False)
        
        logger.debug(f"🔹 Executing Dynatrace API request")
        logger.debug(f"🔹 URL: {url}")
        logger.debug(f"🔹 Payload: {payload}")
        logger.debug(f"🔹 Headers: {headers}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Check if this is a DQL query (needs POST) or metrics query (needs GET)
                if is_dql_query:
                    # DQL query - use POST with JSON body and Bearer token
                    import json
                    logger.debug(f"📤 Complete POST body: {json.dumps(payload, indent=2)}")
                    response = await client.post(url, headers=headers, json=payload)
                else:
                    # Simple metrics query - use GET with query parameters and Api-Token
                    response = await client.get(url, headers=headers, params=payload)
                logger.info(f"📡 Dynatrace API response: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"✅ Query successful, response size: {len(str(result))} chars")
                    return result
                elif response.status_code == 202 and is_dql_query:
                    # DQL query started - need to poll for results
                    result = response.json()
                    request_token = result.get("requestToken")
                    if not request_token:
                        raise Exception("No request token received for async DQL query")
                    
                    logger.info(f"🔄 DQL query started, polling for results with token: {request_token[:10]}...")
                    return await self._poll_dql_results(request_token, headers)
                else:
                    error_text = response.text
                    logger.error(f"❌ Dynatrace API error {response.status_code}: {error_text}")
                    raise Exception(f"Dynatrace API error {response.status_code}: {error_text}")
            except httpx.TimeoutException:
                logger.error(f"❌ Dynatrace API request timed out")
                raise Exception("Dynatrace API request timed out")
            except Exception as e:
                logger.error(f"❌ Dynatrace API request failed: {e}")
                raise
    
    async def _poll_dql_results(self, request_token: str, headers: Dict[str, str], max_polls: int = 30, poll_interval: float = 2.0) -> Dict[str, Any]:
        """
        Poll for DQL query results using the request token.
        """
        # Construct polling URL
        poll_url = self.base_url.replace('live.dynatrace.com', 'apps.dynatrace.com')
        poll_url = f"{poll_url.rstrip('/')}/platform/storage/query/v1/query:poll"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for poll_count in range(max_polls):
                try:
                    logger.debug(f"🔄 Polling attempt {poll_count + 1}/{max_polls}")
                    
                    response = await client.get(
                        poll_url,
                        headers=headers,
                        params={"request-token": request_token}
                    )
                    
                    if response.status_code != 200:
                        error_text = response.text
                        logger.error(f"❌ Polling error {response.status_code}: {error_text}")
                        raise Exception(f"Polling error {response.status_code}: {error_text}")
                    
                    result = response.json()
                    state = result.get("state")
                    progress = result.get("progress", 0)
                    
                    logger.info(f"📊 Query state: {state}, progress: {progress}%")
                    
                    if state == "SUCCEEDED":
                        logger.info(f"✅ DQL query completed successfully")
                        return result.get("result", {})
                    elif state in ["FAILED", "CANCELLED"]:
                        logger.error(f"❌ DQL query {state.lower()}")
                        raise Exception(f"DQL query {state.lower()}")
                    elif state in ["RUNNING", "NOT_STARTED"]:
                        # Continue polling
                        if poll_count < max_polls - 1:
                            await asyncio.sleep(poll_interval)
                        continue
                    else:
                        logger.error(f"❌ Unknown query state: {state}")
                        raise Exception(f"Unknown query state: {state}")
                
                except httpx.TimeoutException:
                    logger.error(f"❌ Polling request timed out")
                    raise Exception("Polling request timed out")
            
            # Max polls reached
            logger.error(f"❌ Query polling timed out after {max_polls} attempts")
            raise Exception(f"Query polling timed out after {max_polls} attempts")
    
    async def execute_queries_batch(
        self, 
        queries: List[Dict[str, Any]], 
        batch_size: int = 10,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple Dynatrace queries in batches.
        """
        logger.info(f"🔹 Starting batch execution of {len(queries)} queries")
        logger.info(f"🔹 Batch size: {batch_size}, Max concurrent: {max_concurrent}")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def execute_single_query(query_obj: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                tile_id = query_obj["tile_id"]
                tile_title = query_obj["tile_title"]
                logger.info(f"🔹 Executing query for tile {tile_id}: '{tile_title}'")
                
                try:
                    result = await self.execute_query(
                        query_obj["query"],
                        **query_obj.get("query_settings", {})
                    )
                    logger.info(f"✅ Query successful for tile {tile_id}")
                    return {
                        "tile_id": tile_id,
                        "tile_title": tile_title,
                        "visualization": query_obj["visualization"],
                        "query": query_obj["query"],
                        "matchMetricPattern": query_obj.get("matchMetricPattern"),
                        "omitGroupByVariableFromMetricName": query_obj.get("omitGroupByVariableFromMetricName"),
                        "dashboard_label": query_obj.get("dashboard_label"),
                        "dashboard_uid": query_obj.get("dashboard_uid"),
                        "result": result,
                        "error": None
                    }
                except Exception as e:
                    logger.error(f"❌ Query failed for tile {tile_id}: {e}")
                    return {
                        "tile_id": tile_id,
                        "tile_title": tile_title,
                        "visualization": query_obj["visualization"],
                        "query": query_obj["query"],
                        "matchMetricPattern": query_obj.get("matchMetricPattern"),
                        "omitGroupByVariableFromMetricName": query_obj.get("omitGroupByVariableFromMetricName"),
                        "dashboard_label": query_obj.get("dashboard_label"),
                        "dashboard_uid": query_obj.get("dashboard_uid"),
                        "result": None,
                        "error": str(e)
                    }
        
        # Process queries in batches
        total_batches = (len(queries) + batch_size - 1) // batch_size
        logger.info(f"🔹 Processing {total_batches} batches")
        
        for i in range(0, len(queries), batch_size):
            batch_num = (i // batch_size) + 1
            batch = queries[i:i + batch_size]
            logger.info(f"🔹 Processing batch {batch_num}/{total_batches} with {len(batch)} queries")
            
            batch_tasks = [execute_single_query(query) for query in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            
            logger.info(f"✅ Completed batch {batch_num}/{total_batches}")
        
        successful_queries = len([r for r in results if r["error"] is None])
        failed_queries = len([r for r in results if r["error"] is not None])
        logger.info(f"📊 Batch execution complete: {successful_queries} successful, {failed_queries} failed")
        
        return results


async def query_dynatrace_dashboard_data(
    dashboard_queries: List[Dict[str, Any]],
    base_url: str,
    api_token: str,
    platform_token: str = None,
    batch_size: int = 10,
    max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """
    Query Dynatrace API for dashboard data.
    """
    client = DynatraceAPIClient(base_url, api_token, platform_token)
    return await client.execute_queries_batch(
        dashboard_queries,
        batch_size=batch_size,
        max_concurrent=max_concurrent
    )