from log import *

from jigsawwm import daemon


class SyncthingService(daemon.ProcessService):
    name = "syncthing"
    args = [
        r"C:\Users\Klesh\Programs\syncthing\syncthing.exe",
        "-no-browser",
        "-no-restart",
        "-no-upgrade",
    ]
    log_path = r"C:\Users\Klesh\Programs\syncthing\syncthing.log"


daemon.register(SyncthingService)

if __name__ == "__main__":
    daemon.message_loop()
