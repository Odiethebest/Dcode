"""Indexing pipeline orchestration — implements DESIGN.md §2.1.

Six stages, advanced as a strict monotonic state machine:
`queued → cloning → parsing → embedding → graphing → ready`
(or `→ failed` at any point, with error context preserved per D-2.1.4).
"""

import json
import logging

from dcode_worker.context import PipelineContext
from dcode_worker.stages import chunk, clone, embed, graph, parse

logger = logging.getLogger("dcode.worker.pipeline")


async def handle_job(message_body: bytes) -> None:
    """Top-level handler for one RabbitMQ message.

    TODO(M1): deserialize message, advance Repo.status between stages,
    persist chunks/symbols/edges, update Redis `job:{repo_id}` key per
    DESIGN.md §3.3.
    """
    try:
        payload = json.loads(message_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.error("malformed job message; discarding")
        return

    repo_id = payload.get("repo_id")
    repo_url = payload.get("url")
    if not repo_id or not repo_url:
        logger.error("job missing repo_id/url: %s", payload)
        return

    logger.info("received indexing job repo_id=%s", repo_id)
    ctx = PipelineContext(repo_id=repo_id, repo_url=repo_url)

    # TODO(M1): run stages in order and advance Repo.status between each.
    #   ctx = await clone.run(ctx)
    #   ctx = await parse.run(ctx)
    #   ctx = await chunk.run(ctx)
    #   ctx = await embed.run(ctx)
    #   ctx = await graph.run(ctx)
    _ = (clone, parse, chunk, embed, graph)  # keep imports live for M1 wiring
    _ = ctx
