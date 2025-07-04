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

from fastapi import APIRouter

from . import data, health, manage

router = APIRouter()
router.include_router(health.router, prefix="", tags=["Health"])
router.include_router(data.router, prefix="/data", tags=["Metrics data pipelines"])
router.include_router(manage.router, prefix="/manage", tags=["Manage"])
