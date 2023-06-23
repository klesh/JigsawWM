from jigsawwm import daemon


class SyncthingService(daemon.ProcessService):
    name = "syncthing"
    args = [
        r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.exe",
        "-no-browser",
        "-no-restart",
        "-no-upgrade",
    ]
    log_path = r"C:\Programs\syncthing-windows-amd64-v1.23.2\syncthing.log"


daemon.register(SyncthingService)

if __name__ == "__main__":
    daemon.message_loop()
