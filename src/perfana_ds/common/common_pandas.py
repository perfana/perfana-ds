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

import pandas as pd


def update_dict(d: dict, path, value):
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def df_to_formatted_json(df, drop_na: bool = None):
    result: dict[int, Any] = {}
    for column in df:
        path = column.split(".")
        values = df[column].to_list()
        for i in range(len(values)):
            update_dict(result.setdefault(i, {}), path, values[i])
    return list(result.values())


#
# def df_to_formatted_json(df, sep=".", drop_na: bool = True):
#     """
#     The opposite of json_normalize
#     """
#     if not any(["." in col for col in df.columns]):
#         return df.to_dict(orient="records")
#
#     result = []
#     for idx, row in df.iterrows():
#         parsed_row: dict[str, Any] = {}
#         if drop_na is True:
#             row = row.dropna()  # noqa
#
#         for col_label, v in row.items():
#             keys = col_label.split(sep)
#
#             current = parsed_row
#             for i, k in enumerate(keys):
#                 if i == len(keys) - 1:
#                     current[k] = v
#                 else:
#                     if k not in current.keys():
#                         current[k] = {}
#                     current = current[k]
#         # save
#         result.append(parsed_row)
#     return result


def exclude_rampup_from_dataframe(
    df_panel_metrics: pd.DataFrame, ramp_up_column: str = "ramp_up"
) -> pd.DataFrame:
    return df_panel_metrics.loc[~df_panel_metrics[ramp_up_column].astype(bool)]


def columns_to_camelcase(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.replace(
        "_(.)", lambda x: x.group(1).upper(), regex=True
    )
    return df


def round_to_multiple(series: pd.Series, multiple: int):
    return series.div(multiple).round().mul(multiple)


def left_filter_groups(
    df_left: pd.DataFrame, df_right: pd.DataFrame, on: list[str]
) -> pd.DataFrame:
    left_index = df_left[on].drop_duplicates().set_index(on).index
    right_index = df_right[on].drop_duplicates().set_index(on).index
    intersection_index = left_index.intersection(right_index)
    df_right = df_right.set_index(on).loc[intersection_index].reset_index()
    return df_left, df_right
