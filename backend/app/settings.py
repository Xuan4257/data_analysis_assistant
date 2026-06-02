from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
TASKS_DIR = DATA_DIR / "tasks"
CONFIG_PATH = DATA_DIR / "config.json"
DATABASE_PATH = DATA_DIR / "tasks.db"

ALLOWED_EXTENSIONS = {".csv", ".json", ".xls", ".xlsx"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

