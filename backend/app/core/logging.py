"""Configuration de logging.

Préfère loguru si dispo (format coloré, structuré JSON optionnel). Sinon fallback
sur stdlib logging avec un format proche, pour ne pas bloquer l'import dans un
environnement minimal.
"""
from __future__ import annotations

import logging as stdlib_logging
import sys
from typing import Any

try:
    from loguru import logger as _loguru_logger  # type: ignore[import-not-found]

    _LOGURU = True
except ImportError:  # pragma: no cover
    _LOGURU = False
    _loguru_logger = None  # type: ignore[assignment]


_CONFIGURED = False


class _StdlibAdapter:
    """Adaptateur minimal qui imite l'API loguru utilisée dans le projet."""

    def __init__(self, logger: stdlib_logging.Logger, extra: dict[str, Any] | None = None) -> None:
        self._logger = logger
        self._extra = extra or {"request_id": "-"}

    def bind(self, **kwargs: Any) -> "_StdlibAdapter":
        merged = {**self._extra, **kwargs}
        return _StdlibAdapter(self._logger, merged)

    def _format(self, message: str, *args: Any) -> str:
        try:
            rendered = message.format(*args) if args else message
        except (IndexError, KeyError):
            rendered = message
        prefix = f"[{self._extra.get('request_id', '-')}] "
        return prefix + rendered

    def info(self, message: str, *args: Any) -> None:
        self._logger.info(self._format(message, *args))

    def warning(self, message: str, *args: Any) -> None:
        self._logger.warning(self._format(message, *args))

    def error(self, message: str, *args: Any) -> None:
        self._logger.error(self._format(message, *args))

    def exception(self, message: str, *args: Any) -> None:
        self._logger.exception(self._format(message, *args))


_stdlib_logger = stdlib_logging.getLogger("healthai")


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    if _LOGURU:
        _loguru_logger.remove()
        if json_logs:
            _loguru_logger.add(sys.stdout, level=level, serialize=True, backtrace=False, diagnose=False)
        else:
            _loguru_logger.add(
                sys.stdout,
                level=level,
                colorize=True,
                backtrace=False,
                diagnose=False,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
                    "<level>{level: <7}</level> "
                    "<cyan>{extra[request_id]}</cyan> "
                    "<level>{message}</level>"
                ),
            )
        _loguru_logger.configure(extra={"request_id": "-"})
    else:
        handler = stdlib_logging.StreamHandler(sys.stdout)
        handler.setFormatter(stdlib_logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s"))
        _stdlib_logger.handlers = [handler]
        _stdlib_logger.setLevel(level)
        _stdlib_logger.propagate = False

    _CONFIGURED = True


def bind_context(**kwargs: Any):
    if _LOGURU:
        return _loguru_logger.bind(**kwargs)
    return _StdlibAdapter(_stdlib_logger).bind(**kwargs)
