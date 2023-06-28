import logging

from jmk import *
from services import *
from tasks import *
from wm import *

from jigsawwm import daemon

logging.basicConfig(level=logging.DEBUG, filename="jigsaw.log")
logFormatter = logging.Formatter(
    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

fileHandler = logging.FileHandler("jmk.log", mode="w")
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)
daemon.message_loop()

daemon.message_loop()
