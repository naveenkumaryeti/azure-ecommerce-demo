"""Audit events: one JSON blob per event (unique name) -> no append conflicts between instances."""
import logging
import socket
import uuid
from datetime import datetime, timezone

import config
from services import blob_service as bs

log = logging.getLogger(__name__)


def log_event(event, details=None):
    ts = datetime.now(timezone.utc)
    name = f"{ts:%Y/%m/%d}/{ts:%H%M%S%f}-{uuid.uuid4().hex[:8]}-{event}.json"
    rec = {"event": event, "timestamp": ts.isoformat(), "instance": socket.gethostname(), "details": details or {}}
    try:
        bs.put_json(config.CONTAINERS["audit"], name, rec)
    except Exception as e:  # never break the request because auditing failed
        log.warning("audit write failed (%s): %s", event, e)
