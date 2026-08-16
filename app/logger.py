import logging
import json
import sys
from datetime import datetime, timezone
from app.config import settings

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            payload.update(record.extra_data)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)

logger = logging.getLogger("caca_auth")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.propagate = False

def log(level: str, message: str, **extra):
    getattr(logger, level.lower())(message, extra={"extra_data": extra})