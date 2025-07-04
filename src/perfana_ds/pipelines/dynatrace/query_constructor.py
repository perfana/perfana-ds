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

from typing import Any
import re
import logging
from datetime import datetime, timezone

from perfana_ds.schemas.dynatrace.dashboard import Dashboard
from perfana_ds.schemas.dynatrace.tile import DataTile
from perfana_ds.schemas.perfana.test_runs import TestRun
from perfana_ds.catalog.catalog import get_catalog

logger = logging.getLogger(__name__)


def construct_dynatrace_queries_from_collection(
    test_run: TestRun,
    dashboard_uid: str = None,
    **kwargs: Any
) -> list[dict[str, Any]]:
    """
    Extract and construct Dynatrace queries from dynatraceDql collection.
    
    Args:
        test_run: Test run object containing application, testEnvironment, and timing information
        dashboard_uid: Optional specific dashboard UID to filter (if None, gets all dashboards)
        **kwargs: Additional arguments
        
    Returns:
        List of query dictionaries ready for execution
    """
    # Extract application and testEnvironment from the TestRun object to ensure consistency
    application = test_run.application
    test_environment = test_run.testEnvironment
    
    logger.info(f"🔹 Constructing queries from dynatraceDql collection for {application}.{test_environment}")
    logger.debug(f"🔹 Using TestRun: {test_run.testRunId}")
    
    # Get catalog and collection
    catalog = get_catalog()
    collection = catalog.dynatrace_dql.collection
    
    # Build query filter using camelCase field names from TestRun properties
    query_filter = {
        "application": application,
        "testEnvironment": test_environment
    }
    
    if dashboard_uid:
        query_filter["dashboardUid"] = dashboard_uid
        logger.info(f"🔹 Filtering for specific dashboard: {dashboard_uid}")
    
    # Query the collection
    logger.debug(f"🔹 Querying collection with filter: {query_filter}")
    dql_documents = list(collection.find(query_filter))
    
    if not dql_documents:
        logger.warning(f"⚠️ No DQL queries found for {application}.{test_environment}" + 
                      (f".{dashboard_uid}" if dashboard_uid else ""))
        return []
    
    logger.info(f"📋 Found {len(dql_documents)} DQL queries in collection")
    
    # No variables used in queries (as per requirement)
    
    queries = []
    
    for dql_doc in dql_documents:
        # Use camelCase field names from the new schema
        panel_title = dql_doc["panelTitle"]
        dashboard_label = dql_doc["dashboardLabel"]
        dashboard_uid = dql_doc["dashboardUid"]
        
        # Generate a tile_id from the MongoDB _id for backwards compatibility
        tile_id = str(dql_doc["_id"])
        
        logger.debug(f"🔹 Processing query: {panel_title}")
        logger.debug(f"🔹 Dashboard: {dashboard_label}")
        
        # Extract the base query and pattern
        query = dql_doc["dqlQuery"]
        match_pattern = dql_doc.get("matchMetricPattern")
        omit_fields = dql_doc.get("omitGroupByVariableFromMetricName", [])
        logger.debug(f"🔹 Original query: {query[:200]}...")
        logger.info(f"🔹 Match pattern from collection: {match_pattern} (type: {type(match_pattern)})")
        logger.debug(f"🔹 Omit fields from metric name: {omit_fields}")
        
        # Replace time range with test run times (no variable replacement needed)
        final_query = _replace_time_range_in_query(query, test_run)
        logger.debug(f"🔹 Final query: {final_query[:200]}...")
        
        # Create query object
        query_obj = {
            "tile_id": tile_id,
            "tile_title": panel_title,
            "query": final_query,
            "visualization": "timeseries",  # Default visualization since we removed this field
            "dashboard_label": dashboard_label,
            "dashboard_uid": dashboard_uid,
            "query_settings": {},  # Default empty settings
            "matchMetricPattern": match_pattern,  # Pass regex pattern for metric filtering
            "omitGroupByVariableFromMetricName": omit_fields  # Pass fields to omit from metric names
        }
        
        queries.append(query_obj)
        logger.info(f"✅ Added query for '{panel_title}' from dashboard '{dashboard_label}' with pattern: {match_pattern}")
    
    logger.info(f"📋 Generated {len(queries)} queries from dynatraceDql collection")
    return queries


def construct_dynatrace_queries_from_dashboard(
    dashboard: Dashboard,
    test_run: TestRun,
    **kwargs: Any
) -> list[dict[str, Any]]:
    """
    Extract and construct Dynatrace queries from dashboard tiles.
    """
    logger.info(f"🔹 Constructing queries from dashboard with {len(dashboard.tiles)} tiles")
    queries = []
    
    # No variables used in queries (as per requirement)
    
    for tile_id, tile in dashboard.tiles.items():
        logger.debug(f"🔹 Processing tile {tile_id}: {getattr(tile, 'title', 'No title')}")
        
        if hasattr(tile, 'query') and tile.query:
            logger.info(f"✅ Found query in tile {tile_id}")
            # Extract the base query
            query = tile.query
            logger.debug(f"🔹 Original query: {query[:200]}...")
            
            # Replace time range with test run times (no variable replacement needed)
            final_query = _replace_time_range_in_query(query, test_run)
            logger.debug(f"🔹 Final query: {final_query[:200]}...")
            
            # Create query object
            query_obj = {
                "tile_id": tile_id,
                "tile_title": getattr(tile, 'title', ''),
                "query": final_query,
                "visualization": getattr(tile, 'visualization', 'timeseries'),
                "query_settings": getattr(tile, 'querySettings', {}).__dict__ if hasattr(getattr(tile, 'querySettings', {}), '__dict__') else {}
            }
            
            queries.append(query_obj)
            logger.info(f"✅ Added query for tile {tile_id}: '{query_obj['tile_title']}'")
        else:
            logger.debug(f"⚠️ Tile {tile_id} has no query or empty query")
    
    logger.info(f"📋 Generated {len(queries)} queries from dashboard")
    return queries


def _replace_time_range_in_query(query: str, test_run: TestRun) -> str:
    """
    Replace time range patterns in Dynatrace query with test run times using proper DQL syntax.
    """
    # Format timestamps as ISO strings for DQL
    # Test run times are already stored as correct UTC times
    # Just use them directly
    start_utc = test_run.start
    end_utc = test_run.end
    
    # Ensure they have UTC timezone info
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
        end_utc = end_utc.replace(tzinfo=timezone.utc)
    
    start_timestamp = start_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    end_timestamp = end_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    
    logger.debug(f"Test run times: {test_run.start} to {test_run.end}")
    logger.debug(f"Converted to DQL: {start_timestamp} to {end_timestamp}")
    
    # More precise regex to remove only incorrectly placed from/to after limit commands
    # This pattern looks for ", from:" after numbers (like "limit 20, from:")
    query = re.sub(r'(\|\s*limit\s+\d+),\s*from:\s*[^,\n\|]+', r'\1', query)
    query = re.sub(r'(\|\s*limit\s+\d+),\s*to:\s*[^,\n\|]+', r'\1', query)
    
    # Also remove standalone ", from:" and ", to:" at end of lines
    query = re.sub(r',\s*from:\s*["\'][^"\']*["\'](?=\s*$)', '', query, flags=re.MULTILINE)
    query = re.sub(r',\s*to:\s*["\'][^"\']*["\'](?=\s*$)', '', query, flags=re.MULTILINE)
    
    # Replace "from: -2m" patterns in timeseries block with actual timestamps
    query = re.sub(r'from:\s*-\d+[mhd]', f'from: "{start_timestamp}"', query)
    
    # Replace any numeric timestamps with quoted ISO strings in timeseries block
    query = re.sub(r'from:\s*(\d+)', f'from: "{start_timestamp}"', query)
    query = re.sub(r'to:\s*(\d+)', f'to: "{end_timestamp}"', query)
    
    # Add time range to timeseries block if no time range is specified anywhere
    if 'from:' not in query:
        # Insert time range into the timeseries block
        if 'timeseries {' in query:
            # Add time range after the closing brace of timeseries block
            query = re.sub(
                r'(timeseries\s*\{[^}]+\})',
                rf'\1, from: "{start_timestamp}", to: "{end_timestamp}"',
                query
            )
        else:
            # If no timeseries block, this might not be a DQL query that needs time range
            pass
    
    return query


def construct_dynatrace_api_url(base_url: str, query: str) -> str:
    """
    Construct the Dynatrace API URL based on query type.
    """
    # Remove trailing slash if present
    base_url = base_url.rstrip('/')
    
    # Check if this is a DQL query (contains 'timeseries' or pipeline operators)
    if 'timeseries' in query.lower() or '|' in query:
        # Use Grail DQL query execution endpoint
        # Convert base URL from live.dynatrace.com to apps.dynatrace.com for Grail
        if 'live.dynatrace.com' in base_url:
            base_url = base_url.replace('live.dynatrace.com', 'apps.dynatrace.com')
        return f"{base_url}/platform/storage/query/v1/query:execute"
    else:
        # Use simple metrics query endpoint
        return f"{base_url}/api/v2/metrics/query"



def prepare_dynatrace_query_payload(query: str, **kwargs: Any) -> dict[str, Any]:
    """
    Prepare the payload for Dynatrace API request based on query type.
    """
    # Check if this is a DQL query
    if 'timeseries' in query.lower() or '|' in query:
        # Get system timezone dynamically for DQL queries
        import datetime
        local_tz = datetime.datetime.now().astimezone().tzinfo
        timezone_name = str(local_tz)
        
        # Convert common timezone names
        if 'CEST' in timezone_name or 'CET' in timezone_name:
            timezone_name = "Europe/Amsterdam"  # or Europe/Berlin, Europe/Paris
        
        # DQL query payload with timezone and default timeframe
        payload = {
            "query": query,
            "timezone": timezone_name
        }
        
        # Add default timeframe if provided
        if "defaultTimeframeStart" in kwargs:
            payload["defaultTimeframeStart"] = kwargs["defaultTimeframeStart"]
        if "defaultTimeframeEnd" in kwargs:
            payload["defaultTimeframeEnd"] = kwargs["defaultTimeframeEnd"]
            
        return payload
    else:
        # Simple metrics query parameters
        return {
            "metricSelector": query,
            "resolution": kwargs.get("resolution", "1m"),
            "from": kwargs.get("from", "now-2h"),
            "to": kwargs.get("to", "now")
        }