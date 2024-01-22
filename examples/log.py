import logging
import os

# import sys

# sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


logFormatter = logging.Formatter(
    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
rootLogger = logging.getLogger()

fileHandler = logging.FileHandler("jigsaw.log", mode="w", encoding="utf-8")
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

if os.environ.get("DEBUG_JIGSAWWM"):
    rootLogger.setLevel(logging.DEBUG)
