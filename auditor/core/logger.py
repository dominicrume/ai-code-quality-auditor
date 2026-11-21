"""Structured logging for the auditor. One channel for runs, one for analyzers."""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        # stderr, never stdout. Logs are diagnostics, and stdout is a channel
        # other things own: the MCP server speaks JSON-RPC on it, and a piped
        # `--json` mode has to stay machine-readable. A single warning about an
        # unparseable file on stdout corrupts the stream and a client drops the
        # connection. A StreamHandler also captures the stream object when it is
        # built, so rebinding sys.stdout later does not move it; getting this
        # right here is the only durable fix.
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
