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

from pydantic import BaseModel

from perfana_ds.schemas.base_document import BaseDocument


def get_model_fields(model: BaseModel, parent_name=None, by_alias: bool = True):
    fields = []
    for name, field in model.__fields__.items():
        field_annotation = field.annotation

        full_name = field.alias if by_alias is True else name
        if parent_name:
            full_name = f"{parent_name}.{full_name}"

        try:
            if issubclass(field_annotation, BaseDocument):
                fields.extend(
                    get_model_fields(field_annotation, full_name, by_alias=by_alias)
                )
            else:
                fields.append(full_name)
        except TypeError:
            fields.append(full_name)

    return fields
