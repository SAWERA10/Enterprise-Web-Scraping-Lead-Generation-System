import logging
from pathlib import Path

OUTPUT_DIR = Path("output")
LOG_FILE = OUTPUT_DIR / "logs.txt"


def setup():
    OUTPUT_DIR.mkdir(exist_ok=True)


def get_logger():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
    )
    return logging.getLogger() 