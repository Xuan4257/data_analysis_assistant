import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .schemas import ApiConfigInput, CleaningConfirmation
from .settings import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, TASKS_DIR, ensure_runtime_dirs
from .store import TaskStore
from .services.cleaning import build_cleaning_proposal
from .services.config_service import load_config, public_config, save_config
from .services.data_loader import dataframe_preview, load_dataframe
from .services.llm import test_connection
from .services.pipeline import run_analysis


ensure_runtime_dirs()
store = TaskStore()
app = FastAPI(title="Insight Forge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
REPORT_PREVIEW_LIMIT = 4000


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", name)
    return name or "uploaded_data.csv"


def _public_task(task: dict[str, Any], include_result: bool = True) -> dict[str, Any]:
    public = {
        key: value
        for key, value in task.items()
        if key not in {"raw_path", "task_dir", "result_zip", "error_trace"}
    }
    if not include_result:
        public.pop("result", None)
        public.pop("proposal", None)
        public.pop("preview", None)
    return public


def _get_task_or_404(task_id: str) -> dict[str, Any]:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    return task


def _output_file(task: dict[str, Any], relative_path: str) -> Path:
    output_dir = (Path(task["task_dir"]) / "output").resolve()
    requested = (output_dir / relative_path).resolve()
    if output_dir != requested and output_dir not in requested.parents:
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    return requested


def _report_file(task: dict[str, Any]) -> Path:
    if task.get("status") != "completed":
        raise HTTPException(status_code=409, detail="报告尚未生成")
    return _output_file(task, "report.md")


def _report_preview(content: str) -> str:
    section_boundary = content.find("\n## 5. 回归诊断结果")
    if 0 < section_boundary <= REPORT_PREVIEW_LIMIT:
        return content[:section_boundary].rstrip()
    return content[:REPORT_PREVIEW_LIMIT].rstrip()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return public_config()


@app.put("/api/config")
def update_config(config: ApiConfigInput) -> dict[str, Any]:
    return save_config(config.model_dump())


@app.post("/api/config/test")
def check_config() -> dict[str, str]:
    try:
        message = test_connection()
        return {"status": "ok", "message": message}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"连接失败：{exc}") from exc


@app.get("/api/config/status")
def get_config_status() -> dict[str, str]:
    try:
        test_connection()
        return {"status": "connected", "message": "连接成功"}
    except Exception as exc:
        return {"status": "failed", "message": f"连接失败：{exc}"}


@app.get("/api/tasks")
def list_tasks() -> list[dict[str, Any]]:
    return [_public_task(task, include_result=False) for task in store.list()]


@app.post("/api/tasks/upload")
async def upload_task(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = _safe_filename(file.filename or "uploaded_data.csv")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 CSV、Excel 和 JSON 文件")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 50 MB 限制")

    task_id = uuid.uuid4().hex[:12]
    task_dir = TASKS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    raw_path = task_dir / filename
    raw_path.write_bytes(content)
    try:
        frame = load_dataframe(raw_path)
        if frame.empty:
            raise ValueError("上传的数据文件为空")
        proposal = build_cleaning_proposal(frame)
        preview = dataframe_preview(frame)
    except Exception as exc:
        raw_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}") from exc

    task = store.create(
        {
            "id": task_id,
            "filename": filename,
            "status": "awaiting_confirmation",
            "progress": 6,
            "stage": "等待确认清洗建议和回归变量",
            "raw_path": str(raw_path),
            "task_dir": str(task_dir),
            "proposal": proposal,
            "preview": preview,
        }
    )
    return _public_task(task)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    return _public_task(_get_task_or_404(task_id))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str) -> dict[str, str]:
    task = _get_task_or_404(task_id)
    if task["status"] in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="分析任务正在运行，暂时无法删除")
    tasks_dir = TASKS_DIR.resolve()
    task_dir = Path(task["task_dir"]).resolve()
    if task_dir == tasks_dir or tasks_dir not in task_dir.parents:
        raise HTTPException(status_code=400, detail="非法任务目录")
    if task_dir.exists():
        shutil.rmtree(task_dir)
    store.delete(task_id)
    return {"status": "deleted", "task_id": task_id}


@app.post("/api/tasks/{task_id}/analyze")
def start_analysis(task_id: str, request: CleaningConfirmation, background_tasks: BackgroundTasks) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    if task["status"] == "running":
        raise HTTPException(status_code=409, detail="分析任务正在运行")
    if task["status"] == "completed":
        raise HTTPException(status_code=409, detail="分析任务已完成，请重新上传文件以调整方案")
    column_names = {column["name"] for column in task["proposal"]["columns"]}
    if request.target_column not in column_names:
        raise HTTPException(status_code=400, detail="请选择有效的目标列")
    accepted = {item["id"] for item in task["proposal"]["suggestions"]}
    if not set(request.accepted_suggestion_ids).issubset(accepted):
        raise HTTPException(status_code=400, detail="清洗建议列表包含无效项目")
    store.update(
        task_id,
        status="queued",
        progress=8,
        stage="分析任务已进入队列",
        analysis_request=request.model_dump(),
        error=None,
    )
    background_tasks.add_task(run_analysis, task_id, store)
    return _public_task(_get_task_or_404(task_id))


@app.get("/api/tasks/{task_id}/files/{relative_path:path}")
def download_output_file(task_id: str, relative_path: str) -> FileResponse:
    task = _get_task_or_404(task_id)
    return FileResponse(_output_file(task, relative_path))


@app.get("/api/tasks/{task_id}/report/preview")
def get_report_preview(task_id: str) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    content = _report_file(task).read_text(encoding="utf-8")
    preview = _report_preview(content)
    return {
        "task_id": task_id,
        "is_preview": preview != content,
        "content": preview,
        "full_report_available": True,
    }


@app.get("/api/tasks/{task_id}/report")
def get_full_report(task_id: str) -> dict[str, Any]:
    task = _get_task_or_404(task_id)
    return {
        "task_id": task_id,
        "is_preview": False,
        "content": _report_file(task).read_text(encoding="utf-8"),
        "full_report_available": True,
    }


@app.get("/api/tasks/{task_id}/report/download")
def download_report(task_id: str) -> FileResponse:
    task = _get_task_or_404(task_id)
    return FileResponse(
        _report_file(task),
        filename=f"{task_id}_report.md",
        media_type="text/markdown; charset=utf-8",
    )


@app.get("/api/tasks/{task_id}/download")
def download_results(task_id: str) -> FileResponse:
    task = _get_task_or_404(task_id)
    if task.get("status") != "completed" or not task.get("result_zip"):
        raise HTTPException(status_code=409, detail="结果压缩包尚未生成")
    return FileResponse(
        task["result_zip"],
        filename=f"{task_id}_analysis_results.zip",
        media_type="application/zip",
    )
