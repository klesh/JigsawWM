import logging

from jmk import *
from services import *
from tasks import *
from wm import *

from jigsawwm import daemon

logging.basicConfig(level=logging.DEBUG)
daemon.message_loop()
