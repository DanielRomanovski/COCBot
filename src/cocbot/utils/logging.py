"""Loguru logger configuration."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logger(log_level: str = "INFO", log_file: str = "logs/cocbot.log") -> None:
    """
    Configure loguru with:
    - Coloured output to stdout
    - Rotating file output to log_file
    """
    # Remove default handler
    logger.remove()

    # Stdout handler
    logger.add(
        sys.stdout,
        level=log_level.upper(),
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # File handler (rotating, 10 MB max, 7 days retention)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_file,
        level=log_level.upper(),
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
    )

    logger.info("Logger initialised — level={}", log_level.upper())
