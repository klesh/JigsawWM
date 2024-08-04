import logging
import os

# import sys

# sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


logFormatter = logging.Formatter(
    "%(asctime)s [%(name)s] [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
fileHandler = logging.FileHandler("jigsaw.log", mode="w", encoding="utf-8")
fileHandler.setFormatter(logFormatter)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)

rootLogger = logging.getLogger()
rootLogger.addHandler(fileHandler)
rootLogger.addHandler(consoleHandler)

debugging = os.environ.get("DEBUG_JIGSAWWM")
if debugging:
    rootLogger.setLevel(logging.DEBUG)
    if debugging != "*":

        loggers = set(debugging.split(","))
        def f(record: logging.LogRecord) -> bool:
            return any(record.name.startswith(logger) for logger in loggers)

        consoleHandler.addFilter(f)
        fileHandler.addFilter(f)
else:
    rootLogger.setLevel(logging.INFO)
