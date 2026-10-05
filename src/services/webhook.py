import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


class WebhookService:
    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.webhook_timeout
        self._max_retries = settings.webhook_max_retries

    async def deliver(self, url: str, payload: dict[str, Any]) -> None:
        attempt_deliver = retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=2, min=2, max=16),
            reraise=True,
        )(self._post)

        await attempt_deliver(url, payload)

    async def _post(self, url: str, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Webhook delivered to %s [HTTP %d]", url, response.status_code)
