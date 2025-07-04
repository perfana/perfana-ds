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

from enum import Enum
from typing import Optional


class ResultStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    RETRY = "RETRY"
    UNKNOWN = "UNKNOWN"
    RESTART = "RESTART"


class AggregationType(str, Enum):
    MIN = "min"
    MAX = "max"
    AVG = "avg"
    MEAN = "mean"
    LAST = "last"
    FIT = "fit"
    MEDIAN = "median"
    STD = "std"
    Q10 = "q10"
    Q25 = "q25"
    Q75 = "q75"
    Q90 = "q90"
    Q95 = "q95"
    Q99 = "q99"

    @classmethod
    def from_original_name(cls, original_name: str) -> Optional["AggregationType"]:
        mapping = {
            "min": cls.MIN,
            "max": cls.MAX,
            "avg": cls.AVG,
            "mean": cls.MEAN,
            "last": cls.LAST,
            "fit": cls.FIT,
            "median": cls.MEDIAN,
            "std": cls.STD,
            "q10": cls.Q10,
            "q25": cls.Q25,
            "q75": cls.Q75,
            "q90": cls.Q90,
            "q95": cls.Q95,
            "q99": cls.Q99,
        }
        return mapping.get(original_name)


class PanelType(str, Enum):
    GRAPH = "graph"
    TABLE_OLD = "table-old"
    TABLE = "table"
    STAT = "stat"
    SINGLESTAT = "singlestat"
    TIME_SERIES = "timeseries"
    UNKNOWN = "unknown"

    @classmethod
    def from_original_name(cls, original_name: str) -> Optional["PanelType"]:
        mapping = {
            "graph": cls.GRAPH,
            "table-old": cls.TABLE_OLD,
            "table": cls.TABLE,
            "stat": cls.STAT,
            "singlestat": cls.SINGLESTAT,
            "timeseries": cls.TIME_SERIES,
            "unknown": cls.UNKNOWN,
        }
        if not original_name:
            print("[PanelType] from_original_name called with empty value")
            return None
        key = original_name.lower()
        result = mapping.get(key)
        return result


class RequirementOperator(str, Enum):
    LT = "lt"  # less than
    GT = "gt"  # greater than

    @property
    def description(self) -> str:
        descriptions = {
            "lt": "less than",
            "gt": "greater than",
        }
        return descriptions[self.value]

    def name_and_description(self) -> str:
        return f"'{self.value}' ({self.description})"


class BenchmarkOperator(str, Enum):
    PST = "pst"  # positive allowed absolute
    NGT = "ngt"  # negative allowed absolute
    PSTPCT = "pst-pct"  # positive allowed percentage
    NGTPCT = "ngt-pct"  # negative allowed percentage

    @property
    def description(self) -> str:
        descriptions = {
            "pst": "positive allowed absolute",
            "ngt": "negative allowed absolute",
            "pst-pct": "positive allowed percentage",
            "ngt-pct": "negative allowed percentage",
        }
        return descriptions[self.value]

    def name_and_description(self) -> str:
        return f"'{self.value}' ({self.description})"
