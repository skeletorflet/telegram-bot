import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

JOBS_DIR = Path(__file__).resolve().parents[2] / "data" / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

def get_job(message_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene la información de un trabajo por message_id"""
    job_file = JOBS_DIR / f"{message_id}.json"
    if job_file.exists():
        try:
            return json.loads(job_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def save_job(message_id: int, data: Dict[str, Any]) -> None:
    """Guarda la información de un trabajo"""
    job_file = JOBS_DIR / f"{message_id}.json"
    job_data = data.copy()
    job_data["timestamp"] = time.time()
    job_file.write_text(json.dumps(job_data, ensure_ascii=False, indent=2), encoding="utf-8")

def delete_job(message_id: int) -> None:
    """Elimina la información de un trabajo"""
    job_file = JOBS_DIR / f"{message_id}.json"
    if job_file.exists():
        job_file.unlink()