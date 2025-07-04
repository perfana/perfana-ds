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

from pymongo.collection import Collection

from perfana_ds.schemas.changepoint import Changepoint
from perfana_ds.schemas.perfana.test_runs import TestRun


def find_most_recent_changepoint(
    test_run: TestRun,
    test_runs_collection: Collection,
    changepoints_collection: Collection,
) -> Changepoint | None:
    base_filters = {
        "application": test_run.application,
        "testEnvironment": test_run.testEnvironment,
        "testType": test_run.testType,
    }

    cursor = changepoints_collection.find(base_filters)
    changepoint_docs = list(cursor)
    changepoints = [Changepoint.model_validate(doc) for doc in changepoint_docs]
    if len(changepoints) == 0:
        return None

    changepoint_test_run_ids = [changepoint.test_run_id for changepoint in changepoints]
    latest_test_run_doc = test_runs_collection.find_one(
        {
            "testRunId": {"$in": changepoint_test_run_ids},
            "start": {"$lte": test_run.start},
        },
        sort={"start": -1},
    )
    if latest_test_run_doc is None:
        return None

    latest_changepoints = [
        changepoint
        for changepoint in changepoints
        if changepoint.test_run_id == latest_test_run_doc["testRunId"]
    ]
    latest_changepoint = latest_changepoints[0]
    return latest_changepoint
