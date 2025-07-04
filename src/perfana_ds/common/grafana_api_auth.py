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


def get_grafana_api_key_from_mongo(grafanas_collection: Collection) -> str:
    token_document = grafanas_collection.find_one()
    if token_document is None:
        raise FileNotFoundError(
            f"Could not get Grafana API key from {grafanas_collection.full_name} collection."
        )
    api_key = token_document["apiKey"]
    return api_key


def create_grafana_api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
