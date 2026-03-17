import subprocess
import platform
from pathlib import Path
from pomo.utils import DATA_DIR
from pomo.settings import get_config


def play_sound(sound_type: str, fallback_file: str):
    if platform.system() != "Linux":
        return

    config = get_config()
    custom_path = config.get("sounds", {}).get(sound_type, "")

    if custom_path:
        target_path = Path(custom_path)
        if target_path.exists():
            subprocess.Popen(
                ["aplay", "-q", str(target_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

    default_path = DATA_DIR / "sounds" / fallback_file
    if default_path.exists():
        subprocess.Popen(
            ["aplay", "-q", str(default_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def notify(
    title: str,
    message: str,
    sound_type: str = "work_done",
    fallback_sound: str = "bell.wav",
):
    if platform.system() == "Linux":
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Pomo Planner", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    play_sound(sound_type, fallback_sound)
