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

import asyncio
import logging
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx


def run_async(coro: Coroutine):
    try:
        # workaround to allow running async from Jupyter notebooks as well
        asyncio.get_running_loop()
        with ThreadPoolExecutor(1) as pool:
            responses = pool.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        # this is run without an existing event loop, i.e. "normally"
        responses = asyncio.run(coro)
    return responses


async def _get_requests_async(
    base_url,
    get_requests: list[dict[str, Any]],
    client_headers: dict[str, Any] | None = None,
    client_kwargs: dict[str, Any] | None = None,
    return_exceptions: bool = True,
):
    client_kwargs = client_kwargs or {}
    transport = httpx.AsyncHTTPTransport(retries=3)
    logger = logging.getLogger("perfana_ds.common.async_requests")
    async with (
        httpx.AsyncClient(
            base_url=base_url,
            headers=client_headers,
            limits=httpx.Limits(max_connections=3),
            transport=transport,
            **client_kwargs,
        ) as client,
    ):
        tasks = []
        for get_request in get_requests:
            logger.debug(
                f"Preparing GET request: base_url={base_url}, get_request={get_request}, headers={client_headers}"
            )
            task = client.get(**get_request)
            tasks.append(task)
        logger.debug(f"Sending {len(tasks)} GET requests to Grafana...")
        try:
            responses = await asyncio.gather(
                *tasks, return_exceptions=return_exceptions
            )
            for i, resp in enumerate(responses):
                if isinstance(resp, Exception):
                    logger.error(
                        f"Exception in GET request {get_requests[i]}: {type(resp)} - {resp}"
                    )
                else:
                    logger.debug(
                        f"Response for GET {get_requests[i]}: status={resp.status_code}"
                    )
        except Exception as e:
            logger.error(f"Exception during async GET requests: {e}")
            raise
    return responses


def get_requests_async(
    base_url,
    get_requests: list[dict[str, Any]],
    client_headers: dict[str, Any] | None = None,
    client_kwargs: dict[str, Any] | None = None,
    return_exceptions: bool = True,
):
    coro = _get_requests_async(
        base_url=base_url,
        get_requests=get_requests,
        client_headers=client_headers,
        client_kwargs=client_kwargs,
        return_exceptions=return_exceptions,
    )
    responses = run_async(coro)
    return responses


async def _post_requests_async(
    base_url,
    post_requests: list[dict[str, Any]],
    client_headers: dict[str, Any] = None,
    client_kwargs: dict[str, Any] = None,
    return_exceptions: bool = True,
):
    client_kwargs = client_kwargs or {}
    async with (
        httpx.AsyncClient(
            base_url=base_url,
            headers=client_headers,
            limits=httpx.Limits(max_connections=10),
            **client_kwargs,
        ) as client,
    ):
        tasks = []
        for post_request in post_requests:
            task = client.post(**post_request)
            tasks.append(task)
        responses = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    return responses


def post_requests_async(
    base_url,
    post_requests: list[dict[str, Any]],
    client_headers: dict[str, Any] = None,
    client_kwargs: dict[str, Any] = None,
    return_exceptions: bool = True,
):
    coro = _post_requests_async(
        base_url=base_url,
        post_requests=post_requests,
        client_headers=client_headers,
        client_kwargs=client_kwargs,
        return_exceptions=return_exceptions,
    )
    responses = run_async(coro)
    return responses
