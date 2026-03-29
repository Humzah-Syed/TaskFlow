import json
import logging
from datetime import datetime, timezone
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
tea_logger = logging.getLogger("taskflow")


def log_pack(event: str, **fields: Any) -> None:
    blob = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    tea_logger.info(json.dumps(blob, default=str))
