import json
from pathlib import Path

USER_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "users"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS = {
    "sampler_name": "LCM",
    "scheduler": "",
    "steps": 4,
    "cfg_scale": 1.0,
    "aspect_ratio": "1:1",
    "base_size": 512,
    "n_iter": 1,
    "pre_mode": "none",
    "pre_value": "",
    "post_mode": "none",
    "post_value": "",
    "loras": [],
}

PRESETS_PRE = [
    "masterpiece, best quality, ultra-detailed",
    "best quality, 4k, uhd",
    "photorealistic, high detail",
    "cinematic lighting, dramatic shadows",
]

PRESETS_POST = [
    "in a tower",
    "studio lighting",
    "volumetric lighting",
    "highly detailed background",
]

def load_user_settings(user_id: int) -> dict:
    fp = USER_DATA_DIR / f"{user_id}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_user_settings(user_id: int, settings: dict) -> None:
    fp = USER_DATA_DIR / f"{user_id}.json"
    fp.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")