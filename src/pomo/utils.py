from pathlib import Path
import importlib.resources as pkg_resources
from platformdirs import user_data_dir, user_state_dir
import subprocess
import platform
import time

APP_NAME = "pomo"
DATA_DIR = Path(user_data_dir(APP_NAME))
STATE_DIR = Path(user_state_dir(APP_NAME))


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    sounds_dir = DATA_DIR / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundled_sounds = pkg_resources.files("pomo") / "sounds"
        if bundled_sounds.is_dir():
            for audio_file in bundled_sounds.iterdir():
                if audio_file.name.endswith(".wav"):
                    dest = sounds_dir / audio_file.name
                    if not dest.exists():
                        dest.write_bytes(audio_file.read_bytes())
    except Exception:
        pass


def get_db_path() -> Path:
    return DATA_DIR / "pomo.db"


def get_socket_path() -> Path:
    return STATE_DIR / "pomo.sock"


def spawn_daemon_in_background():
    cmd = ["pomo", "daemon"]
    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                cmd,
                creationflags=0x00000008,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        time.sleep(1.0)
    except Exception as e:
        print(f"Failed to auto-spawn daemon: {e}")
