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
    """Create the necessary XDG directories and extract default sounds."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    sounds_dir = DATA_DIR / "sounds"
    sounds_dir.mkdir(parents=True, exist_ok=True)

    # Extract bundled sounds from the Python package to the local user directory
    try:
        bundled_sounds = pkg_resources.files("pomo") / "sounds"
        if bundled_sounds.is_dir():
            for audio_file in bundled_sounds.iterdir():
                if audio_file.name.endswith(".wav"):
                    dest = sounds_dir / audio_file.name
                    # Only copy if the user hasn't already modified/deleted it
                    if not dest.exists():
                        dest.write_bytes(audio_file.read_bytes())
    except Exception:
        pass  # Fail gracefully if no bundled sounds are found


def get_db_path() -> Path:
    return DATA_DIR / "pomo.db"


def get_socket_path() -> Path:
    return STATE_DIR / "pomo.sock"


def spawn_daemon_in_background():
    """Silently spawns the daemon process detached from the current terminal."""
    # We use 'pomo' directly since 'uv tool install' puts it in the PATH
    cmd = ["pomo", "daemon"]

    try:
        if platform.system() == "Windows":
            # DETACHED_PROCESS prevents the new process from attaching to the console
            subprocess.Popen(
                cmd,
                creationflags=0x00000008,  # DETACHED_PROCESS
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # start_new_session=True (POSIX) detaches it completely so it survives terminal closure
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        # Give the daemon 1 second to boot up and create the socket
        time.sleep(1.0)
    except Exception as e:
        print(f"Failed to auto-spawn daemon: {e}")
