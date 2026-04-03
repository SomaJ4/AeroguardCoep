import asyncio
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from models.schemas import AnalyzeResult

VISION_SERVICE_URL: str = os.environ.get("VISION_SERVICE_URL", "http://localhost:8001")
VISION_SERVICE_MAX_RETRIES: int = int(os.environ.get("VISION_SERVICE_MAX_RETRIES", "3"))
VISION_SERVICE_RETRY_DELAY_SECONDS: float = float(os.environ.get("VISION_SERVICE_RETRY_DELAY_SECONDS", "1.0"))
VISION_SERVICE_TIMEOUT_SECONDS: float = float(os.environ.get("VISION_SERVICE_TIMEOUT_SECONDS", "30.0"))


class VisionServiceError(Exception):
    """Base exception for all Vision Service client errors."""


class VisionServiceClientError(VisionServiceError):
    """Raised on HTTP 400 or 424 — bad request, no retry."""
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Vision Service returned {status_code}: {body}")


class VisionServiceServerError(VisionServiceError):
    """Raised on HTTP 500 — server error, no retry."""
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Vision Service server error {status_code}: {body}")


class VisionServiceUnavailableError(VisionServiceError):
    """Raised when all 503 retries are exhausted."""
    def __init__(self, attempts: int):
        self.attempts = attempts
        super().__init__(f"Vision Service unavailable after {attempts} attempt(s)")


class VisionServiceTimeoutError(VisionServiceError):
    """Raised when the Vision Service does not respond within the timeout."""
    def __init__(self):
        super().__init__("Vision Service request timed out")



async def analyze(
    stream_url: str,
    camera_id: str,
    session_id: str,
    lat: float,
    lng: float,
) -> "AnalyzeResult":
    """
    Call the Vision Service POST /analyze endpoint.

    Retry on 503 with exponential back-off.
    Raise typed exceptions for all other error cases.
    """
    from models.schemas import AnalyzeResult

    url = f"{VISION_SERVICE_URL}/analyze"
    payload = {
        "stream_url": stream_url,
        "camera_id": camera_id,
        "session_id": session_id,
        "lat": lat,
        "lng": lng,
    }

    attempts = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=VISION_SERVICE_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException:
            raise VisionServiceTimeoutError()

        if response.status_code == 200:
            return AnalyzeResult(**response.json())

        if response.status_code == 503:
            attempts += 1
            if attempts > VISION_SERVICE_MAX_RETRIES:
                raise VisionServiceUnavailableError(attempts=attempts)
            delay = VISION_SERVICE_RETRY_DELAY_SECONDS * (2 ** (attempts - 1))
            await asyncio.sleep(delay)
            continue

        if response.status_code in (400, 424):
            raise VisionServiceClientError(
                status_code=response.status_code,
                body=response.text,
            )

        # 500 and any other unexpected status
        raise VisionServiceServerError(
            status_code=response.status_code,
            body=response.text,
        )
