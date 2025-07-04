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

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.gzip import GZipMiddleware

from perfana_ds import __version__
from perfana_ds.project_settings import get_settings
from perfana_ds_api.routes import router
from perfana_ds_api.tags import API_TAGS

# Configure logging level from environment variable
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

#
# # Add the RichHandler to the logger
# rich_handler = RichHandler(rich_tracebacks=True)
# rich_handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
# logging.getLogger('perfana_ds').addHandler(rich_handler)


class EndpointFilter(logging.Filter):
    """Suppress logs for calls to /health endpoint."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


# Filter out logs for specific endpoint(s)
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    default_response_class=ORJSONResponse,
    version=__version__,
    debug=True,  # returns traceback on-error. As long as the api is not public, this is handy
    openapi_tags=API_TAGS,
)


app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(router)
