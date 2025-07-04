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

from datetime import datetime, timezone

import pandas as pd
from celery.utils.log import get_task_logger
from pydantic import ValidationError

from perfana_ds.pipelines.metrics.clean import (
    add_metric_metadata_to_dataframe,
    combine_duplicate_documents_data,
)
from perfana_ds.schemas.panel_metrics import PanelMetricsDocument
from perfana_ds.schemas.panel_query_result import PrometheusPanelQueryResult
from perfana_ds.schemas.perfana.test_runs import TestRun

logger = get_task_logger(__name__)


def get_columns_from_frame(frame) -> list[str]:
    return [
        (
            field["config"]["displayNameFromDS"]
            if "config" in field.keys() and "displayNameFromDS" in field["config"]
            else field["name"]
        )
        for field in frame["schema"]["fields"]
    ]


def transform_dataframe_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Time -> time and format integer nanoseconds as UTC datetimes."""
    df["Time"] = df["Time"].apply(
        lambda x: datetime.fromtimestamp(x / 1000.0, tz=timezone.utc)
    )
    df = df.rename(columns={"Time": "time"}).set_index("time")
    return df


def create_dataframe_from_frames(frames):
    return pd.DataFrame(
        dict(zip(get_columns_from_frame(frames), frames["data"]["values"]))
    )


def query_response_to_dataframe(
    prometheus_response_json: PrometheusPanelQueryResult, empty_as_none: bool = False
) -> pd.DataFrame | None:
    transformed_dataframes: list[pd.DataFrame] = []
    if (prometheus_response_json.data is not None) and (
        len(prometheus_response_json.data) > 0
    ):
        for result_key, result in prometheus_response_json.data["results"].items():
            if "frames" not in result:
                logger.warning(f"Result {result_key} is missing 'frames': {result}")
                continue
            for frames in result["frames"]:
                df_from_frames = create_dataframe_from_frames(frames)
                string_column_indices = [
                    i
                    for i, schema_field in enumerate(frames["schema"]["fields"])
                    if schema_field["type"].lower() == "string"
                ]
                if len(string_column_indices) > 0:
                    string_columns = [
                        col
                        for i, col in enumerate(df_from_frames.columns)
                        if i in string_column_indices
                    ]
                    df_from_frames = df_from_frames.drop(columns=string_columns)
                if (df_from_frames.shape[0] > 0) and (df_from_frames.shape[1] > 1):
                    transformed_df = transform_dataframe_timestamps(df_from_frames)
                    transformed_dataframes.append(transformed_df)
    df_wide = (
        pd.concat(transformed_dataframes, axis=1)
        if transformed_dataframes
        else pd.DataFrame(data=None)
    )
    df_wide = df_wide.astype(object).pipe(lambda d: d.where(d.notnull(), None))
    df_long = df_wide.melt(ignore_index=False, var_name="metric_name").reset_index()
    if df_long.shape[0] > 0:
        df_long = df_long.sort_values(["metric_name", "time", "value"]).drop_duplicates(
            subset=["time", "metric_name"]
        )
        # Check and Drop Nulls in last frameset item
        if df_long.iloc[-1]["value"] is None:
            df_long = df_long[:-1]
    elif empty_as_none is False:
        df_long = pd.DataFrame(
            {
                "metric_name": pd.NA,
                "time": pd.to_datetime([None], utc=True),
                "value": pd.NA,
            },
            index=[0],
        )
    else:
        df_long = None
    return df_long


def format_prometheus_data_as_dataframe(
    test_run: TestRun, panel_query_responses: list[PrometheusPanelQueryResult]
) -> pd.DataFrame:
    panel_dataframes = []
    for panel_query_response in panel_query_responses:
        df_panel = query_response_to_dataframe(panel_query_response)
        # Skip if dataframe is None
        if df_panel is not None:
            df_panel = add_metric_metadata_to_dataframe(df_panel, test_run=test_run)
            df_panel = df_panel.assign(
                test_run_id=test_run.testRunId,
                dashboard_uid=panel_query_response.dashboard_uid,
                application_dashboard_id=panel_query_response.application_dashboard_id,
                panel_id=panel_query_response.panel_id,
                panel_title=panel_query_response.panel.title,
                dashboard_label=panel_query_response.dashboard_label,
                datasource_type=panel_query_response.datasource_type,
            )
            panel_dataframes.append(df_panel)

    return pd.concat(panel_dataframes, axis=0) if panel_dataframes else pd.DataFrame()


def format_query_responses_as_dataframe(
    test_run: TestRun, panel_query_responses: list[PrometheusPanelQueryResult]
) -> list[PanelMetricsDocument]:
    documents = []
    for panel_query_response in panel_query_responses:
        df_panel = query_response_to_dataframe(panel_query_response, empty_as_none=True)
        if df_panel is None:
            panel_records = []
        else:
            df_panel = add_metric_metadata_to_dataframe(df_panel, test_run=test_run)
            panel_records = df_panel.to_dict(orient="records")

        common_document = {k: v for k, v in panel_query_response if k != "data"}
        common_document.update({"updated_at": datetime.utcnow()})
        try:
            document = PanelMetricsDocument(data=panel_records, **common_document)
        except ValidationError as e:
            raise e
        documents.append(document)

    documents = combine_duplicate_documents_data(
        documents, fields=["test_run_id", "application_dashboard_id", "panel_id"]
    )
    return documents
