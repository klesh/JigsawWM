"""The Window Manager Service"""

from jigsawwm.app.job import Service
from jigsawwm.jmk.jmk_service import JmkService
from jigsawwm.jmk.core import JmkTriggerDefs

from .manager import WindowManager


class WmService(Service):
    """JMK service"""

    name = "Window Manager"
    is_running = False
    hotkeys: JmkTriggerDefs

    def __init__(self, jmk_service: JmkService):
        super().__init__()
        self.manager = WindowManager(jmk_service)
        self.jmk = jmk_service
        self.hotkeys = []

    def start(self):
        self.is_running = True
        self.jmk.hotkeys.register_triggers(self.hotkeys)
        self.manager.start()

    def stop(self):
        self.manager.stop()
        for args in self.hotkeys:
            self.jmk.hotkeys.unregister(args[0])
        self.is_running = False