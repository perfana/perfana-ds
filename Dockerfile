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

##### MAIN API BUILDER #####
#FROM python:3.11 AS base
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as base

ENV ENV=prod
ENV WEB_CONCURRENCY=4

RUN useradd -m dashuser -u 1001

WORKDIR /app

RUN apt-get update -y && apt-get install -y wget

# Add Tini
ARG TARGETPLATFORM
RUN apt-get update -y && apt-get install -y wget; \
    set -e ; \
    version="0.19.0" ; \
    url="https://github.com/krallin/tini/releases/download/v${version}" ; \
    case "$TARGETPLATFORM" in \
      "linux/amd64")   file="tini-amd64" ;; \
      "linux/arm64")   file="tini-arm64" ;; \
       *)              echo "Invalid platform: ${TARGETPLATFORM}" && exit 1 ;; \
    esac ; \
    wget -q -O /tini "${url}/${file}" ; \
    chmod +x /tini; \
    apt-get remove -y wget && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*


ENTRYPOINT ["/tini", "--"]

# Setting environment variable
ENV LANG=C.UTF-8

# Copying source code
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN ls


# https://docs.astral.sh/uv/guides/integration/docker/#installing-a-project
RUN uv sync
ENV PATH="/app/.venv/bin:$PATH"

RUN chown -R dashuser:dashuser /app
USER 1001

EXPOSE 8080
CMD ["uvicorn", "src.perfana_ds_api.app:app", "--host", "0.0.0.0", "--port", "8080"]
