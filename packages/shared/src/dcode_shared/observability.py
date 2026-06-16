"""Small structured-logging helper shared across services."""

from __future__ import annotations

import json
import logging
from typing import Any


def structured_event(event: str, **fields: Any) -> str:
    """Render one JSON log payload with a stable top-level `event` field."""
    return json.dumps({"event": event, **fields}, sort_keys=True, default=str)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit one structured log line at INFO level."""
    logger.info(structured_event(event, **fields))
