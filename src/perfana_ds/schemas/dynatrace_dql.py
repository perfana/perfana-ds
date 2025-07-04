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

from perfana_ds.schemas.base_document import BaseDocument


class DynatraceDqlDocument(BaseDocument):
    """
    Document schema for storing Dynatrace DQL queries extracted from dashboards.
    
    This collection serves as a registry of all DQL queries available for execution,
    allowing for better management and reuse of queries across different test runs.
    """
    
    # Metadata
    application: str                    # e.g., "afterburner"  
    testEnvironment: str               # e.g., "acc", "prod"
    
    # Dashboard information
    dashboardLabel: str                # Human-readable dashboard name
    dashboardUid: str                  # Unique dashboard identifier
    
    # Panel information  
    panelTitle: str                    # Panel/tile title
    
    # Query content
    dqlQuery: str                      # The actual DQL query string
    matchMetricPattern: str = None     # Optional regex pattern to filter metric names
    omitGroupByVariableFromMetricName: list[str] = []  # Fields to exclude from metric name construction
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "application": "afterburner",
                "testEnvironment": "acc",
                "dashboardLabel": "Kubernetes-Node -Pods", 
                "dashboardUid": "kubernetes-node-pods",
                "panelTitle": "CPU Usage per Pod",
                "dqlQuery": "timeseries { cpu_usage = avg(dt.kubernetes.container.cpu_usage) }, by: { dt.entity.cloud_application_instance, k8s.pod.name }, filter: { k8s.cluster.name == $Cluster AND k8s.node.name == $Node }, from: -2m",
                "matchMetricPattern": "cpu_usage.*pod",
                "omitGroupByVariableFromMetricName": ["dt.entity.cloud_application_instance"]
            }
        }