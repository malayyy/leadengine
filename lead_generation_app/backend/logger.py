import json
import os
import logging
import logging.handlers
import time
import traceback
import re
from functools import wraps
from datetime import datetime, timezone
from typing import Optional, Dict, Any

SENSITIVE_PATTERNS = [
    (r'(li_at["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***'),
    (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***'),
    (r'(cookie["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***'),
    (r'(password["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***'),
    (r'(token["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***'),
    (r'(authorization["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+', r'\1***REDACTED***', re.IGNORECASE),
]


def mask_sensitive(data: str) -> str:
    for pattern, replacement, *flags in SENSITIVE_PATTERNS:
        flag = flags[0] if flags else 0
        data = re.sub(pattern, replacement, data, flags=flag)
    return data


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage() if isinstance(record.msg, str) else str(record.msg),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
        "RESET": "\033[0m",
        "GRAY": "\033[90m",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        gray = self.COLORS["GRAY"]
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        msg = record.getMessage()
        log = f"{gray}{ts}{reset} {color}{record.levelname:<5}{reset} {record.name:<15} {msg}"
        if record.exc_info and record.exc_info[0]:
            log += f"\n{''.join(traceback.format_exception(*record.exc_info))}"
        return log


def _make_log_dir(campaign_name: Optional[str] = None) -> str:
    env_dir = os.environ.get("LOG_DIR", "")
    base = (
        env_dir
        if env_dir
        else os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
    )
    if campaign_name:
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', campaign_name)
        path = os.path.join(base, safe)
    else:
        path = base
    os.makedirs(path, exist_ok=True)
    return path


def get_logger(name: str, campaign: Optional[str] = None, level: Optional[int] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = level or getattr(logging, os.environ.get("LOG_LEVEL", "DEBUG").upper())
    logger.setLevel(log_level)
    logger.propagate = False

    log_dir = _make_log_dir(campaign)

    json_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f"{name}.json"),
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
    )
    json_handler.setLevel(log_level)
    json_handler.setFormatter(JSONFormatter())
    logger.addHandler(json_handler)

    text_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=100 * 1024 * 1024,
        backupCount=5,
    )
    text_handler.setLevel(log_level)
    text_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(text_handler)

    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(ConsoleFormatter())
    logger.addHandler(console)

    return logger


def log_duration(logger: logging.Logger, operation: str, level: int = logging.DEBUG):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.monotonic() - start
                logger.log(level, "%s completed in %.3fs", operation, elapsed,
                           extra={"extra_fields": {"operation": operation, "duration_ms": round(elapsed * 1000, 2), "status": "success"}})
                return result
            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error("%s failed after %.3fs: %s", operation, elapsed, str(e),
                             extra={"extra_fields": {"operation": operation, "duration_ms": round(elapsed * 1000, 2), "status": "failed", "error": str(e)}})
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                elapsed = time.monotonic() - start
                logger.log(level, "%s completed in %.3fs", operation, elapsed,
                           extra={"extra_fields": {"operation": operation, "duration_ms": round(elapsed * 1000, 2), "status": "success"}})
                return result
            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error("%s failed after %.3fs: %s", operation, elapsed, str(e),
                             extra={"extra_fields": {"operation": operation, "duration_ms": round(elapsed * 1000, 2), "status": "failed", "error": str(e)}})
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class PhaseLogger:
    def __init__(self, campaign_name: str, job_id: int):
        self.campaign = campaign_name
        self.job_id = job_id
        self.scrape_log = get_logger(f"job_{job_id}_scrape", campaign_name)
        self.enrich_log = get_logger(f"job_{job_id}_enrich", campaign_name)
        self.email_log = get_logger(f"job_{job_id}_email", campaign_name)
        self.db_log = get_logger(f"job_{job_id}_db", campaign_name)
        self.api_log = get_logger(f"job_{job_id}_api", campaign_name)

    def log_scrape(self, msg: str, *args, **extra):
        self.scrape_log.info(msg, *args, extra={"extra_fields": {"job_id": self.job_id, "campaign": self.campaign, **extra}})

    def log_enrich(self, msg: str, *args, **extra):
        self.enrich_log.info(msg, *args, extra={"extra_fields": {"job_id": self.job_id, "campaign": self.campaign, **extra}})

    def log_email(self, msg: str, *args, **extra):
        self.email_log.info(msg, *args, extra={"extra_fields": {"job_id": self.job_id, "campaign": self.campaign, **extra}})

    def log_db(self, msg: str, **extra):
        self.db_log.debug(msg, extra={"extra_fields": {"job_id": self.job_id, "campaign": self.campaign, **extra}})

    def log_api(self, msg: str, **extra):
        self.api_log.info(msg, extra={"extra_fields": {"job_id": self.job_id, "campaign": self.campaign, **extra}})

    def error(self, phase: str, msg: str, exc: Optional[Exception] = None, **extra):
        logger = getattr(self, f"{phase}_log", self.scrape_log)
        extra_fields = {"job_id": self.job_id, "campaign": self.campaign, "phase": phase, **extra}
        if exc:
            logger.error("%s | Exception: %s", msg, str(exc), exc_info=exc,
                         extra={"extra_fields": extra_fields})
        else:
            logger.error(msg, extra={"extra_fields": extra_fields})

