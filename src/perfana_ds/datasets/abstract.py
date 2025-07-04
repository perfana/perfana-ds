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

from typing import TypeVar

from pydantic import BaseModel

BaseModelType = TypeVar("BaseModelType", bound=BaseModel)


class BaseDataset(BaseModel):
    def load(self):
        raise NotImplementedError()

    async def async_load(self):
        raise NotImplementedError()

    def save(self):
        raise NotImplementedError()

    async def async_save(self):
        raise NotImplementedError()
