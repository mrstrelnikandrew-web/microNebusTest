import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.payments import router as payments_router
from src.broker.setup import broker
from src.config import get_settings
from src.database import async_session_factory
from src.services.outbox import OutboxRelayService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_outbox_relay: OutboxRelayService | None = None
_relay_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _outbox_relay, _relay_task

    await broker.start()
    logger.info("Broker connected")

    settings = get_settings()
    if settings.enable_outbox_in_api:
        _outbox_relay = OutboxRelayService(
            session_factory=async_session_factory,
            broker=broker,
        )
        _relay_task = asyncio.create_task(_outbox_relay.start(), name="outbox-relay")
        logger.info("Outbox relay started in API process")

    yield

    if _outbox_relay is not None:
        await _outbox_relay.stop()
    if _relay_task is not None and not _relay_task.done():
        _relay_task.cancel()
        try:
            await _relay_task
        except asyncio.CancelledError:
            pass

    await broker.close()
    logger.info("Broker disconnected")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Payment Processing Service",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(payments_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
