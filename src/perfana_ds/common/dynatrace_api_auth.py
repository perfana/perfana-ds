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


def get_dynatrace_api_token_from_mongo(dynatrace_collection: Collection) -> str:
    token_document = dynatrace_collection.find_one()
    if token_document is None:
        raise FileNotFoundError(
            f"Could not get Dynatrace API token from {dynatrace_collection.full_name} collection."
        )
    api_token = token_document["apiToken"]
    return api_token


def create_dynatrace_api_headers(token: str, use_bearer: bool = False) -> dict[str, str]:
    """
    Create headers for Dynatrace API requests.
    
    Args:
        token: The API token
        use_bearer: If True, use Bearer token (for Grail/Platform APIs), 
                   if False, use Api-Token (for legacy APIs)
    """
    auth_header = f"Bearer {token}" if use_bearer else f"Api-Token {token}"
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": auth_header,
    }