import json
from pathlib import Path
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("pomo"))
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "defaults": {"pomos": 4, "work_mins": 25, "break_mins": 5},
    "sounds": {
        "work_done": "",
        "break_done": "",
        "task_done": "",
        "reminder": "",
    },
}


def get_config() -> dict:
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            user_config = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            for k, v in user_config.items():
                if isinstance(v, dict):
                    merged[k].update(v)
            return merged
    except Exception:
        return DEFAULT_CONFIG


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
