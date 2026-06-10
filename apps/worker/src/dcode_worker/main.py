"""Index worker entrypoint — consumes RabbitMQ jobs and runs the indexing pipeline.

Implements DESIGN.md §2.1. Skeleton: connects, declares queue, logs each
received job and acks it. Real pipeline execution lands at M1.
"""

import asyncio
import logging

import aio_pika

from dcode_worker.pipeline import handle_job
from dcode_worker.settings import worker_settings

logger = logging.getLogger("dcode.worker")


async def consume_loop() -> None:
    connection = await aio_pika.connect_robust(worker_settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(worker_settings.queue_name, durable=True)
        logger.info("subscribed to %s", worker_settings.queue_name)

        async with queue.iterator() as messages:
            async for message in messages:
                async with message.process():
                    await handle_job(message.body)


def main() -> None:
    logging.basicConfig(level=worker_settings.log_level.upper())
    logger.info("Dcode index worker starting (queue=%s)", worker_settings.queue_name)
    try:
        asyncio.run(consume_loop())
    except KeyboardInterrupt:
        logger.info("worker stopped by signal")


if __name__ == "__main__":
    main()
