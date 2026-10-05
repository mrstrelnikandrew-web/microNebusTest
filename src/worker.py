import asyncio
import logging

from faststream import FastStream

from src.broker.consumer import broker  # noqa: F401
from src.broker.setup import broker as _broker
from src.database import async_session_factory
from src.services.outbox import OutboxRelayService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

faststream_app = FastStream(_broker)


async def main() -> None:
    relay = OutboxRelayService(
        session_factory=async_session_factory,
        broker=_broker,
    )

    relay_task = asyncio.create_task(relay.start(), name="outbox-relay")

    try:
        await faststream_app.run()
    finally:
        await relay.stop()
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        logger.info("Worker shutdown completed")


if __name__ == "__main__":
    asyncio.run(main())
