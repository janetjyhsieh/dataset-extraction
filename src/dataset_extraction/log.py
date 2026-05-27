import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path | None = None) -> None:
    """Configure the dataset_extraction logger.

    Args:
        log_dir: Directory for the rotating log file. If None, only the
                 console handler is attached (useful for short commands).
    """
    logger = logging.getLogger("dataset_extraction")
    logger.setLevel(logging.DEBUG)

    # Add console handler only if one isn't already present.
    has_console = any(
        type(h) is logging.StreamHandler for h in logger.handlers
    )
    if not has_console:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        logger.addHandler(console)

    # Add file handler only if log_dir is given and we're not already
    # writing to that same file.
    if log_dir is not None:
        log_file = Path(log_dir) / "pipeline.log"
        already_filing = any(
            isinstance(h, RotatingFileHandler)
            and Path(h.baseFilename) == log_file.resolve()
            for h in logger.handlers
        )
        if not already_filing:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                log_file,
                maxBytes=10_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter("%(asctime)s  %(name)s  %(levelname)s  %(message)s")
            )
            logger.addHandler(fh)
