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

import logging
import os
from urllib.parse import parse_qs, urlparse

from celery.app import Celery
from celery.signals import after_setup_logger, task_prerun
from celery.utils.log import get_task_logger

from perfana_ds.project_settings import get_settings

# Configure logging level from environment variable for Celery worker
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

task_logger = get_task_logger(__name__)


def create_celery_app():
    settings = get_settings()

    parsed_url = urlparse(settings.MONGO_URL)
    params = parse_qs(parsed_url.query)

    broker_transport_options = {"default_database": settings.MONGO_DB}
    # broker_transport_options = {}  # TODO: comment before pushing, is for debugging

    broker_transport_options["ttl"] = True

    # catch SSL/TLS options from url for broker options
    if "ssl" in params.keys():
        broker_transport_options["ssl"] = params["ssl"][0]

    # SSL options is deprecated in favor of TLS and must be equal, so set both if TLS option is found
    if "tls" in params.keys():
        broker_transport_options["tls"] = params["tls"][0]
        broker_transport_options["ssl"] = params["tls"][0]

    celery = Celery(
        __name__,
        broker=settings.MONGO_URL,
        broker_transport_options=broker_transport_options,
        backend=settings.MONGO_URL,
        mongodb_backend_settings={
            "database": settings.MONGO_DB,
            "taskmeta_collection": "dsCeleryTasks",
            "options": {"connectTimeoutMS": 3000, "tz_aware": True, "connect": False},
        },
        worker_hijack_root_logger=False,
        # worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s[%(task_id)s]: %(message)s",
        worker_task_log_format=(
            "%(asctime)s - %(levelname)s - %(task_name)s[%(task_id)s] - %(message)s - [%(name)s:%(lineno)d]"
        ),
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        task_queues={
            "celery": {
                "exchange": "celery",
                "routing_key": "celery",
            },
            "metrics": {
                "exchange": "metrics",
                "routing_key": "metrics",
            },
        },
    )
    return celery


@after_setup_logger.connect
def on_after_setup_logger(**kwargs):
    # Configure logging level from environment variable
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level, logging.INFO)
    
    logger = logging.getLogger("celery")
    logger.propagate = True
    logger.setLevel(level)
    
    logger = logging.getLogger("celery.app.trace")
    logger.propagate = True
    logger.setLevel(level)
    
    # Also set level for perfana_ds loggers
    perfana_logger = logging.getLogger("perfana_ds")
    perfana_logger.setLevel(level)


@task_prerun.connect
def on_task_prerun(**kwargs):
    args = kwargs.get("args", [])
    kwargs = kwargs.get("kwargs", {})
    task_logger.info(f"Task starting with {args=}, {kwargs=}")


# asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
worker = create_celery_app()
worker.autodiscover_tasks(
    packages=[
        "perfana_ds_api.routes.data",
    ],
    related_name=None,
    force=True,
)
