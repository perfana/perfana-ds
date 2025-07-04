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

from datetime import datetime
from typing import Any

from bson import ObjectId
from celery.utils.log import get_task_logger
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic.json_schema import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonSchemaMode,
    JsonSchemaValue,
)
from pydantic_core import core_schema

logger = get_task_logger(__name__)


def map_type(t):
    type_mapping = {"float": "double", "integer": "number", "boolean": "bool"}
    return type_mapping.get(t, t)


def replace_with_ref(d):
    if isinstance(d, dict):
        if "$ref" in d.keys():
            return d["$ref"]
        else:
            return {key: replace_with_ref(value) for key, value in d.items()}
    elif isinstance(d, list):
        return [replace_with_ref(x) for x in d]
    else:
        return d


def build_properties_schema(d, defs: dict):
    if not isinstance(d, dict):
        return d

    type_val = d.pop("type", None)
    format_val = d.pop("format", None)
    if format_val == "date-time":
        type_val = "date"
    if isinstance(type_val, str):
        d["bsonType"] = map_type(type_val)

    _ = d.pop("default", None)

    result = {}
    for key, value in d.items():
        if key == "$ref":
            def_key = value.split("/")[-1]
            logger.debug(f"building {def_key} for {key}")
            d[key] = build_properties_schema(defs[def_key], defs=defs)

    for key, value in d.items():
        if key in ["const", "additionalProperties"]:
            continue

        if isinstance(value, dict):
            result[key] = build_properties_schema(value, defs=defs)
        elif isinstance(value, list):
            result[key] = [build_properties_schema(x, defs=defs) for x in value]
        else:
            result[key] = value

    result = replace_with_ref(result)
    return result


def create_mongodb_schema(model: type[BaseModel]):
    json_schema = model.model_json_schema()
    defs = json_schema.get("$defs", {})
    properties = json_schema.get("properties", {})
    mongo_properties = build_properties_schema(properties, defs=defs)
    _ = mongo_properties.pop("_id", None)
    mongodb_schema = {
        "$jsonSchema": {
            "required": json_schema.get("required", []),
            "properties": mongo_properties,
        }
    }
    return mongodb_schema


class GenerateJsonSchemaMongo(GenerateJsonSchema):
    def is_instance_schema(
        self, schema: core_schema.IsInstanceSchema
    ) -> JsonSchemaValue:
        if schema["cls"] is ObjectId:
            return {"type": "objectId"}
        else:
            return super().is_instance_schema(schema)


class BaseDocument(BaseModel):
    """Base document to store in mongo using camelCase when saving."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @classmethod
    def mongodb_schema(cls):
        return create_mongodb_schema(cls)

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchemaMongo,
        mode: JsonSchemaMode = "validation",
    ) -> dict[str, Any]:
        return super().model_json_schema(by_alias, ref_template, schema_generator, mode)


class BasePanelDocument(BaseDocument):
    """Base document that pertains to a single dashboard panel."""

    test_run_id: str
    application_dashboard_id: str
    dashboard_uid: str
    panel_id: int
    panel_title: str
    dashboard_label: str
    updated_at: datetime | None = None


class BaseMetricDocument(BaseDocument):
    """Base document that pertains to a single dashboard panel."""

    test_run_id: str
    application_dashboard_id: str
    panel_id: int
    metric_name: str
    updated_at: datetime | None = None


class BaseMetricCompareDocument(BaseMetricDocument):
    """Base document that pertains to a single dashboard panel."""

    baseline_run_id: str
    updated_at: datetime | None = None
