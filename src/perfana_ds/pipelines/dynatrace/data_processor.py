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

from typing import Any, Dict, List
from datetime import datetime
import logging
import pandas as pd
import re

from perfana_ds.schemas.panel_document import PanelDocument
from perfana_ds.schemas.panel_query_result import DynatracePanelQueryResult
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument

logger = logging.getLogger(__name__)


def _matches_metric_pattern(metric_name: str, pattern: str) -> bool:
    """
    Check if a metric name matches the given regex pattern.
    
    Args:
        metric_name: The metric name to check
        pattern: The regex pattern to match against (can be None)
        
    Returns:
        True if pattern is None or if metric_name matches the pattern
    """
    if not pattern:
        return True
    
    try:
        return bool(re.search(pattern, metric_name))
    except re.error as e:
        logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        return True  # If pattern is invalid, don't filter


def _parse_dql_grouping_fields(query: str) -> List[str]:
    """
    Parse DQL query to extract grouping fields from the 'by:' clause.
    
    Args:
        query: DQL query string
        
    Returns:
        List of original field names from the by: clause
    """
    try:
        # Match: by: { field1, field2, field3 }
        by_pattern = r'by:\s*\{\s*([^}]+)\s*\}'
        by_match = re.search(by_pattern, query, re.IGNORECASE)
        
        if not by_match:
            return []
        
        # Extract and clean field names
        fields_str = by_match.group(1)
        fields = [field.strip() for field in fields_str.split(',')]
        
        logger.debug(f"Extracted grouping fields from DQL: {fields}")
        logger.debug(f"DQL query excerpt: ...{query[max(0, len(query)-200):]}")
        return fields
        
    except Exception as e:
        logger.warning(f"Failed to parse DQL grouping fields: {e}")
        return []


def _has_fields_add(query: str) -> bool:
    """
    Check if the DQL query contains fieldsAdd operations.
    
    Args:
        query: DQL query string
        
    Returns:
        True if query contains fieldsAdd operations
    """
    return "fieldsAdd" in query.lower()


def _parse_fields_add_names(query: str) -> List[str]:
    """
    Parse DQL query to extract field names added by fieldsAdd operations.
    
    Args:
        query: DQL query string
        
    Returns:
        List of field names added by fieldsAdd operations
    """
    try:
        fields_add_names = []
        
        # Match: fieldsAdd fieldName = "value" or fieldsAdd fieldName = expression
        fields_add_pattern = r'fieldsAdd\s+([^=\s]+)\s*='
        
        for match in re.finditer(fields_add_pattern, query, re.IGNORECASE):
            field_name = match.group(1).strip()
            fields_add_names.append(field_name)
        
        logger.debug(f"Extracted fieldsAdd field names from DQL: {fields_add_names}")
        return fields_add_names
        
    except Exception as e:
        logger.warning(f"Failed to parse DQL fieldsAdd operations: {e}")
        return []


def _parse_dql_field_renames(query: str) -> Dict[str, str]:
    """
    Parse DQL query to extract field rename mappings from 'fieldsRename' operations.
    
    Args:
        query: DQL query string
        
    Returns:
        Dictionary mapping original field names to renamed field names
    """
    try:
        rename_mappings = {}
        
        # Match: fieldsRename `NewName` = old_field_name
        # Also handle: fieldsRename NewName = old_field_name (without backticks)
        rename_pattern = r'fieldsRename\s+`?([^`=\s]+)`?\s*=\s*([^,\n\|]+)'
        
        for match in re.finditer(rename_pattern, query, re.IGNORECASE):
            new_name = match.group(1).strip()
            old_name = match.group(2).strip()
            rename_mappings[old_name] = new_name
        
        logger.debug(f"Extracted field renames from DQL: {rename_mappings}")
        return rename_mappings
        
    except Exception as e:
        logger.warning(f"Failed to parse DQL field renames: {e}")
        return {}


def _get_grouping_field_values(record: Dict[str, Any], query: str) -> List[str]:
    """
    Extract grouping field values from a DQL response record using the original query.
    
    Args:
        record: Single record from DQL response
        query: Original DQL query string
        
    Returns:
        List of grouping field values in the order they appear in the by: clause
    """
    try:
        # Get original grouping fields from by: clause
        grouping_fields = _parse_dql_grouping_fields(query)
        if not grouping_fields:
            return []
        
        # Get field rename mappings
        field_renames = _parse_dql_field_renames(query)
        
        # Extract values for grouping fields
        grouping_values = []
        logger.debug(f"Processing grouping fields: {grouping_fields}")
        logger.debug(f"Field renames: {field_renames}")
        logger.debug(f"Available record fields: {list(record.keys())}")
        
        for original_field in grouping_fields:
            # Check if field was renamed
            actual_field = field_renames.get(original_field, original_field)
            
            # Get value from record
            field_value = record.get(actual_field)
            logger.debug(f"Field '{original_field}' -> '{actual_field}' = {field_value}")
            
            if field_value is not None and field_value != "":
                grouping_values.append(str(field_value))
            else:
                logger.warning(f"Missing value for grouping field '{actual_field}' (original: '{original_field}') in record with keys: {list(record.keys())}")
                # Return empty list if any grouping field is missing - this will skip metric creation
                return []
        
        return grouping_values
        
    except Exception as e:
        logger.warning(f"Failed to extract grouping field values: {e}")
        return []


def _is_grouping_field(field_name: str, query: str) -> bool:
    """
    Check if a field is a grouping field based on the DQL query.
    
    Args:
        field_name: Field name to check
        query: DQL query string
        
    Returns:
        True if the field is a grouping field, False otherwise
    """
    try:
        # Get original grouping fields from by: clause
        grouping_fields = _parse_dql_grouping_fields(query)
        if not grouping_fields:
            return False
        
        # Get field rename mappings
        field_renames = _parse_dql_field_renames(query)
        
        # Check if field_name is either an original grouping field OR a renamed grouping field
        for original_field in grouping_fields:
            actual_field = field_renames.get(original_field, original_field)
            # Check both original field name and renamed field name
            if field_name == original_field or field_name == actual_field:
                return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Failed to check if field is grouping field: {e}")
        return False


def process_dynatrace_response_data(
    query_results: List[Dict[str, Any]],
    dashboard_id: str,
    test_run_id: str,
    test_run_end: str = None
) -> tuple[List[PanelDocument], List[PanelMetricsDocument]]:
    """
    Process Dynatrace API response data into PanelDocument and PanelMetricsDocument objects.
    """
    logger.info(f"🔹 Processing {len(query_results)} query results into panel and metrics documents")
    panel_documents = []
    metrics_documents = []
    
    for i, result in enumerate(query_results):
        tile_id = result.get("tile_id", f"unknown_{i}")
        tile_title = result.get("tile_title", "Unknown")
        
        
        logger.debug(f"🔹 Processing result {i+1}/{len(query_results)}: tile {tile_id} '{tile_title}'")
        
        try:
            if result.get("error"):
                logger.warning(f"⚠️ Query error for tile {tile_id}: {result['error']}")
                error_document = _create_error_panel_document(
                    result, dashboard_id, test_run_id, result["error"]
                )
                panel_documents.append(error_document)
            else:
                logger.debug(f"✅ Creating panel document for tile {tile_id}")
                panel_document = _create_panel_document_from_result(
                    result, dashboard_id, test_run_id
                )
                panel_documents.append(panel_document)
                
                # Process DQL results into metrics
                if result.get("result"):
                    logger.debug(f"🔹 Processing DQL results for metrics for tile {tile_id}")
                    metrics_doc = _create_metrics_document_from_dql_result(
                        result, dashboard_id, test_run_id, test_run_end
                    )
                    if metrics_doc:
                        metrics_documents.append(metrics_doc)
                        logger.debug(f"✅ Created metrics document for tile {tile_id}")
                
        except Exception as e:
            logger.error(f"❌ Error processing result for tile {tile_id}: {e}")
            # Create error document for failed processing
            error_document = _create_error_panel_document(
                result, dashboard_id, test_run_id, str(e)
            )
            panel_documents.append(error_document)
    
    logger.info(f"📝 Generated {len(panel_documents)} panel documents and {len(metrics_documents)} metrics documents")
    return panel_documents, metrics_documents


def _create_panel_document_from_result(
    result: Dict[str, Any],
    dashboard_id: str,
    test_run_id: str
) -> PanelDocument:
    """
    Create a PanelDocument from a Dynatrace query result.
    """
    tile_id = result["tile_id"]
    tile_title = result["tile_title"]
    
    # Create panel document
    panel_document = PanelDocument(
        test_run_id=test_run_id,
        application_dashboard_id="dynatrace", 
        dashboard_uid=dashboard_id,
        panel_id=int(tile_id) if tile_id.isdigit() else hash(tile_id) % 2147483647,
        panel_title=tile_title,
        dashboard_label="Dynatrace Dashboard",
        panel={"type": result["visualization"], "title": tile_title, "id": int(tile_id) if tile_id.isdigit() else hash(tile_id) % 2147483647},
        query_variables={},
        datasource_type="dynatrace",
        benchmark_ids=None,
        requests=[],
        errors=None,
        warnings=None
    )
    
    return panel_document


def _create_metrics_document_from_dql_result(
    result: Dict[str, Any],
    dashboard_id: str,
    test_run_id: str,
    test_run_end: str = None
) -> PanelMetricsDocument | None:
    """
    Create a PanelMetricsDocument from DQL query results.
    """
    try:
        tile_id = result["tile_id"]
        tile_title = result["tile_title"]
        dql_result = result["result"]
        query = result.get("query", "")
        match_pattern = result.get("matchMetricPattern")
        omit_from_metric_name = result.get("omitGroupByVariableFromMetricName", [])
        
        logger.info(f"🔍 Data processor received pattern: {match_pattern} (type: {type(match_pattern)}) for tile {tile_id}")
        
        if match_pattern:
            logger.info(f"🔍 Applying metric pattern filter: '{match_pattern}' for tile {tile_id}")
            # Test the pattern with a sample metric name to verify it works
            test_name = "optimus-prime-be-afterburner-98bb97cc-gv9g6_cpu_usage"
            test_result = _matches_metric_pattern(test_name, match_pattern)
            logger.info(f"🔍 Pattern test: '{test_name}' matches '{match_pattern}' = {test_result}")
        else:
            logger.info(f"🔍 No metric pattern filter for tile {tile_id} - processing all metrics")
        
        # Extract records from DQL result
        records = dql_result.get("records", [])
        if not records:
            logger.warning(f"No records found in DQL result for tile {tile_id}")
            logger.debug(f"Complete DQL result: {dql_result}")
            return None
        
        logger.debug(f"Found {len(records)} records for tile {tile_id}")
        if records:
            logger.debug(f"First record structure: {list(records[0].keys())}")
            logger.debug(f"First record sample: {records[0]}")
        
        # Skip the first record if it's a header/schema record (all values are None)
        data_records = records
        if records and all(value is None for value in records[0].values()):
            logger.debug(f"Skipping header record for tile {tile_id}")
            data_records = records[1:]
            logger.debug(f"Using {len(data_records)} data records after skipping header")
        
        if not data_records:
            logger.warning(f"No data records found after filtering for tile {tile_id}")
            return None
        
        # Convert DQL records to metrics data
        metrics_data = []
        seen_metric_names = set()  # Track metric names to detect duplicates
        
        for i, record in enumerate(data_records):
            # Extract timestamp - DQL records may have different timestamp field names
            timestamp = None
            timestamp_field = None
            
            # Check for various timestamp field patterns
            for ts_field in ["timestamp", "timeframe.start", "timeframe", "time", "_time", "dt.timestamp"]:
                if ts_field in record:
                    timestamp = record[ts_field]
                    timestamp_field = ts_field
                    break
            
            # If no explicit timestamp field, check if timeframe object exists
            if not timestamp and "timeframe" in record:
                timeframe = record["timeframe"]
                if isinstance(timeframe, dict):
                    if "start" in timeframe:
                        timestamp = timeframe["start"]
                        timestamp_field = "timeframe.start"
                    elif "end" in timeframe:
                        timestamp = timeframe["end"] 
                        timestamp_field = "timeframe.end"
            
            # For timeseries queries without explicit timestamps, use the test run end time
            if not timestamp:
                logger.debug(f"No timestamp field found in DQL record {i} for tile {tile_id}, using test run end time")
                # Use test run end time as fallback for aggregate queries
                timestamp = test_run_end or "2025-06-30T10:06:06.208000Z"  # Using test run end time
                timestamp_field = "default"
            
            # Parse timestamp
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            elif isinstance(timestamp, (int, float)):
                # Assume Unix timestamp in milliseconds
                timestamp = pd.to_datetime(timestamp, unit='ms')
            elif isinstance(timestamp, dict):
                # Handle timeframe objects that got assigned as timestamp
                if 'start' in timestamp:
                    timestamp = pd.to_datetime(timestamp['start'])
                elif 'end' in timestamp:
                    timestamp = pd.to_datetime(timestamp['end'])
                else:
                    logger.warning(f"Unknown timestamp dict format: {timestamp}")
                    timestamp = pd.to_datetime(test_run_end or "2025-06-30T10:06:06.208000Z")
            
            # Extract grouping field values using the DQL query
            grouping_values = _get_grouping_field_values(record, query)
            
            # Skip this record if any required grouping fields are missing
            if not grouping_values:
                logger.warning(f"Skipping record {i} for tile {tile_id} due to missing grouping field values")
                continue
            
            # Create metric name prefix from grouping fields, excluding omitted fields
            if omit_from_metric_name:
                logger.debug(f"Omitting grouping fields from metric name: {omit_from_metric_name}")
                
                # Get original grouping fields to map values to field names
                grouping_fields = _parse_dql_grouping_fields(query)
                field_renames = _parse_dql_field_renames(query)
                
                # Build filtered grouping values
                filtered_grouping_values = []
                for i, original_field in enumerate(grouping_fields):
                    if i < len(grouping_values):
                        # Check if this field should be omitted
                        actual_field = field_renames.get(original_field, original_field)
                        if original_field not in omit_from_metric_name and actual_field not in omit_from_metric_name:
                            filtered_grouping_values.append(grouping_values[i])
                        else:
                            logger.debug(f"Omitting field '{original_field}' (actual: '{actual_field}') from metric name")
                
                metric_prefix = "_".join(filtered_grouping_values)
                logger.debug(f"Original grouping values: {grouping_values}")
                logger.debug(f"Filtered grouping values: {filtered_grouping_values}")
                logger.debug(f"Generated metric prefix after filtering: '{metric_prefix}'")
            else:
                metric_prefix = "_".join(grouping_values)
                logger.debug(f"Generated metric prefix (no filtering): '{metric_prefix}'")
            
            # Debug logging for metric prefix generation
            logger.debug(f"Record keys: {list(record.keys())}")
            logger.debug(f"Extracted grouping values: {grouping_values}")
            
            # Check if this query has fieldsAdd operations
            has_fields_add = _has_fields_add(query)
            fields_add_names = _parse_fields_add_names(query) if has_fields_add else []
            
            # Get metricName value if present (from fieldsAdd metricName = "value")
            metric_name_from_fields_add = record.get("metricName")
            
            logger.debug(f"Query has fieldsAdd: {has_fields_add}")
            logger.debug(f"FieldsAdd names: {fields_add_names}")
            logger.debug(f"MetricName from fieldsAdd: {metric_name_from_fields_add}")
            
            # Extract metric values from the record
            for field_name, field_value in record.items():
                # Skip timestamp-related fields
                if field_name.startswith(('timestamp', 'timeframe', 'time', '_time', 'dt.timestamp')):
                    continue
                if field_name == timestamp_field:
                    continue
                
                # Skip grouping fields and non-metric fields
                if _is_grouping_field(field_name, query) or field_name in ('timeframe', 'interval'):
                    continue
                
                # If query has fieldsAdd, only process the fieldsAdd fields
                if has_fields_add and field_name not in fields_add_names:
                    logger.debug(f"Skipping field '{field_name}' - not in fieldsAdd list: {fields_add_names}")
                    continue
                
                # Skip metricName field itself (it's metadata, not data)
                if field_name == "metricName":
                    logger.debug(f"Skipping metricName field - using its value as metric name")
                    continue
                
                # Skip intermediate DQL operation fields (valuesOp1, valuesOp2, etc.) 
                # These are temporary calculation results, not final metrics
                if field_name.startswith('valuesOp'):
                    continue
                
                # Handle different value types, including None values and arrays
                if field_value is not None:
                    if isinstance(field_value, list):
                        # Handle arrays of values (timeseries data)
                        # Get interval from record (in nanoseconds)
                        interval_ns = int(record.get("interval", "60000000000"))  # Default 60 seconds
                        interval_seconds = interval_ns / 1_000_000_000  # Convert to seconds
                        
                        # Get start time from timeframe
                        start_time = None
                        if "timeframe" in record and isinstance(record["timeframe"], dict):
                            start_time = pd.to_datetime(record["timeframe"]["start"])
                        else:
                            start_time = pd.to_datetime(timestamp)
                        
                        logger.info(f"🔸 Processing array field '{field_name}' with {len(field_value)} values")
                        logger.info(f"🔸 Interval: {interval_seconds}s, Start time: {start_time}")
                        
                        for idx, value in enumerate(field_value):
                            if isinstance(value, (int, float)) and not pd.isna(value):
                                # Create a separate metric entry for each time point
                                point_timestamp = start_time + pd.Timedelta(seconds=idx * interval_seconds)
                                
                                # Construct metric name: use metricName value if available, otherwise use field name
                                if metric_name_from_fields_add:
                                    # Use metricName value as the actual metric name
                                    metric_name = f"{metric_prefix}_{metric_name_from_fields_add}" if metric_prefix else metric_name_from_fields_add
                                else:
                                    # Use field name as metric name (traditional approach)
                                    metric_name = f"{metric_prefix}_{field_name}" if metric_prefix else field_name
                                
                                # Check for duplicate metric names
                                if metric_name in seen_metric_names:
                                    logger.warning(f"⚠️ Duplicate metric name detected: '{metric_name}' - this may override existing metrics")
                                else:
                                    seen_metric_names.add(metric_name)
                                
                                # Apply metric pattern filtering
                                if _matches_metric_pattern(metric_name, match_pattern):
                                    metrics_data.append({
                                        "metric_name": metric_name,
                                        "time": point_timestamp,
                                        "timestep": idx * interval_seconds,
                                        "ramp_up": False,  # Will be determined based on timestamp
                                        "value": float(value)
                                    })
                                    logger.info(f"✅ ADDED metric: {metric_name} = {value} (matches pattern: {match_pattern})")
                                else:
                                    logger.info(f"❌ FILTERED metric: {metric_name} (doesn't match pattern: {match_pattern})")
                    elif isinstance(field_value, (int, float)) and not pd.isna(field_value):
                        # Single numeric value
                        # Construct metric name: use metricName value if available, otherwise use field name
                        if metric_name_from_fields_add:
                            # Use metricName value as the actual metric name
                            metric_name = f"{metric_prefix}_{metric_name_from_fields_add}" if metric_prefix else metric_name_from_fields_add
                        else:
                            # Use field name as metric name (traditional approach)
                            metric_name = f"{metric_prefix}_{field_name}" if metric_prefix else field_name
                        
                        # Check for duplicate metric names
                        if metric_name in seen_metric_names:
                            logger.warning(f"⚠️ Duplicate metric name detected: '{metric_name}' - this may override existing metrics")
                        else:
                            seen_metric_names.add(metric_name)
                        
                        # Apply metric pattern filtering
                        if _matches_metric_pattern(metric_name, match_pattern):
                            metrics_data.append({
                                "metric_name": metric_name,
                                "time": timestamp,
                                "timestep": 0.0,
                                "ramp_up": False,
                                "value": float(field_value)
                            })
                            logger.info(f"✅ ADDED metric: {metric_name} = {field_value} (matches pattern: {match_pattern})")
                        else:
                            logger.info(f"❌ FILTERED metric: {metric_name} (doesn't match pattern: {match_pattern})")
                    elif isinstance(field_value, str):
                        # Handle string representations of numbers
                        try:
                            metric_value = float(field_value)
                            # Construct metric name: use metricName value if available, otherwise use field name
                            if metric_name_from_fields_add:
                                # Use metricName value as the actual metric name
                                metric_name = f"{metric_prefix}_{metric_name_from_fields_add}" if metric_prefix else metric_name_from_fields_add
                            else:
                                # Use field name as metric name (traditional approach)
                                metric_name = f"{metric_prefix}_{field_name}" if metric_prefix else field_name
                            
                            # Check for duplicate metric names
                            if metric_name in seen_metric_names:
                                logger.warning(f"⚠️ Duplicate metric name detected: '{metric_name}' - this may override existing metrics")
                            else:
                                seen_metric_names.add(metric_name)
                            
                            # Apply metric pattern filtering
                            if _matches_metric_pattern(metric_name, match_pattern):
                                metrics_data.append({
                                    "metric_name": metric_name,
                                    "time": timestamp,
                                    "timestep": 0.0,
                                    "ramp_up": False,
                                    "value": metric_value
                                })
                                logger.info(f"✅ ADDED metric: {metric_name} = {metric_value} (matches pattern: {match_pattern})")
                            else:
                                logger.info(f"❌ FILTERED metric: {metric_name} (doesn't match pattern: {match_pattern})")
                        except (ValueError, TypeError):
                            # Try to parse percentage values
                            if field_value.endswith('%'):
                                try:
                                    metric_value = float(field_value[:-1])
                                    # Construct metric name: use metricName value if available, otherwise use field name
                                    if metric_name_from_fields_add:
                                        # Use metricName value as the actual metric name
                                        metric_name = f"{metric_prefix}_{metric_name_from_fields_add}" if metric_prefix else metric_name_from_fields_add
                                    else:
                                        # Use field name as metric name (traditional approach)
                                        metric_name = f"{metric_prefix}_{field_name}" if metric_prefix else field_name
                                    
                                    # Check for duplicate metric names
                                    if metric_name in seen_metric_names:
                                        logger.warning(f"⚠️ Duplicate metric name detected: '{metric_name}' - this may override existing metrics")
                                    else:
                                        seen_metric_names.add(metric_name)
                                    
                                    # Apply metric pattern filtering
                                    if _matches_metric_pattern(metric_name, match_pattern):
                                        metrics_data.append({
                                            "metric_name": metric_name,
                                            "time": timestamp,
                                            "timestep": 0.0,
                                            "ramp_up": False,
                                            "value": metric_value
                                        })
                                        logger.info(f"✅ ADDED metric: {metric_name} = {metric_value}% (matches pattern: {match_pattern})")
                                    else:
                                        logger.info(f"❌ FILTERED metric: {metric_name} (doesn't match pattern: {match_pattern})")
                                except (ValueError, TypeError):
                                    logger.debug(f"Skipped field {field_name} with unparseable value {field_value}")
                            else:
                                logger.debug(f"Skipped field {field_name} with non-numeric string {field_value}")
                    else:
                        logger.debug(f"Skipped field {field_name} with unsupported type {type(field_value)}: {field_value}")
                else:
                    logger.debug(f"Skipped field {field_name} with None value")
        
        if not metrics_data:
            if match_pattern:
                logger.warning(f"No metric data extracted from DQL result for tile {tile_id} after applying pattern filter '{match_pattern}'")
            else:
                logger.warning(f"No metric data extracted from DQL result for tile {tile_id}")
            return None
        
        if match_pattern:
            logger.info(f"📊 Created {len(metrics_data)} metric data points for tile {tile_id} (after applying pattern filter: '{match_pattern}')")
        else:
            logger.info(f"📊 Created {len(metrics_data)} metric data points for tile {tile_id}")
        
        # Create PanelMetricsDocument
        panel_id = int(tile_id) if tile_id.isdigit() else hash(tile_id) % 2147483647
        
        return PanelMetricsDocument(
            test_run_id=test_run_id,
            application_dashboard_id="dynatrace",
            dashboard_uid=dashboard_id,
            panel_id=panel_id,
            panel_title=tile_title,
            dashboard_label="Dynatrace Dashboard",
            data=metrics_data,
            errors=[],
            benchmark_ids=[]
        )
        
    except Exception as e:
        logger.error(f"Error creating metrics document from DQL result: {e}")
        return None


def _create_error_panel_document(
    result: Dict[str, Any],
    dashboard_id: str,
    test_run_id: str,
    error_message: str
) -> PanelDocument:
    """
    Create an error PanelDocument for failed processing.
    """
    tile_id = result["tile_id"]
    return PanelDocument(
        test_run_id=test_run_id,
        application_dashboard_id="dynatrace",
        dashboard_uid=dashboard_id,
        panel_id=int(tile_id) if tile_id.isdigit() else hash(tile_id) % 2147483647,
        panel_title=result["tile_title"],
        dashboard_label="Dynatrace Dashboard",
        panel={"type": result["visualization"], "title": result["tile_title"], "id": int(tile_id) if tile_id.isdigit() else hash(tile_id) % 2147483647, "error": error_message},
        query_variables={},
        datasource_type="dynatrace",
        benchmark_ids=None,
        requests=[],
        errors=[{"error": error_message}],
        warnings=None
    )


