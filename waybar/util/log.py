import logging
from pathlib import Path


class LevelPadFormatter(logging.Formatter):
    LEVEL_WIDTH = len("WARNING")

    def format(self, record):
        level = record.levelname
        pad = " " * (self.LEVEL_WIDTH - len(level))
        record.padded = f"[{level}]{pad}"
        record.unpadded = f"[{level}]"
        return super().format(record)


def configure(debug: bool, name: str, logfile: Path) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Logs go only to your file
    # No interference from pytest / SwiftBar / root handlers
    # First log line is written immediately
    logger.propagate = False

    # Do not add handlers twice
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        pass

    handler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
    handler.setLevel(level)
    formatter = LevelPadFormatter(
        # f"%(asctime)s %(padded)s {name}.%(funcName)s - %(message)s"
        f"%(asctime)s %(unpadded)s {name}.%(funcName)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


# def configure_logging(debug: bool = False):
#     logging.basicConfig(
#         filename=logfile,
#         filemode="w",  # 'a' = append, 'w' = overwrite
#         format="%(asctime)s [%(levelname)-5s] - %(message)s",
#         level=logging.DEBUG if debug else logging.INFO,
#     )
