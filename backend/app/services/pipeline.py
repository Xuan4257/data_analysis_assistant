import json
import traceback
import zipfile
from pathlib import Path
from typing import Any

from ..store import TaskStore
from .cleaning import apply_cleaning, normalized_columns
from .data_loader import load_dataframe
from .eda import run_eda
from .report import generate_report
from .regression import run_regression


def _resolve_column(column: str, original_columns: list[Any], normalize: bool) -> str:
    if not normalize:
        return column
    mapping = dict(zip([str(item) for item in original_columns], normalized_columns(original_columns)))
    return mapping.get(column, column)


def _zip_outputs(output_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in output_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir))


def run_analysis(task_id: str, store: TaskStore) -> None:
    task = store.get(task_id)
    if task is None:
        return
    try:
        task_dir = Path(task["task_dir"])
        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        store.update(task_id, status="running", progress=12, stage="正在应用已确认的数据清洗方案")
        frame = load_dataframe(Path(task["raw_path"]))
        accepted_ids = task["analysis_request"]["accepted_suggestion_ids"]
        cleaned, cleaning_log = apply_cleaning(frame, accepted_ids)
        cleaned.to_csv(output_dir / "cleaned_data.csv", index=False, encoding="utf-8-sig")

        normalize = "normalize_columns" in accepted_ids
        target = _resolve_column(task["analysis_request"]["target_column"], list(frame.columns), normalize)
        features = [
            _resolve_column(column, list(frame.columns), normalize)
            for column in task["analysis_request"]["feature_columns"]
        ]

        store.update(task_id, progress=32, stage="正在生成探索性分析图表")
        eda = run_eda(cleaned, output_dir, target)
        store.update(task_id, progress=58, stage="正在执行 OLS 诊断与自适应回归优化")
        regression = run_regression(cleaned, output_dir, target, features)
        store.update(task_id, progress=82, stage="正在生成 Markdown 报告")
        report = generate_report(
            output_dir,
            task["filename"],
            cleaning_log,
            eda,
            regression,
            proposal=task.get("proposal"),
            cleaning_summary={
                "original_rows": int(len(frame)),
                "cleaned_rows": int(len(cleaned)),
                "original_columns": int(len(frame.columns)),
                "cleaned_columns": int(len(cleaned.columns)),
                "original_missing": int(frame.isna().sum().sum()),
                "cleaned_missing": int(cleaned.isna().sum().sum()),
            },
        )

        result = {
            "cleaning_log": cleaning_log,
            "eda": eda,
            "regression": regression,
            "report_excerpt": report[:2400],
        }
        (output_dir / "analysis_summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        zip_path = task_dir / "analysis_results.zip"
        _zip_outputs(output_dir, zip_path)
        store.update(
            task_id,
            status="completed",
            progress=100,
            stage="分析完成",
            result=result,
            result_zip=str(zip_path),
        )
    except Exception as exc:
        store.update(
            task_id,
            status="failed",
            progress=100,
            stage="分析失败",
            error=str(exc),
            error_trace=traceback.format_exc(),
        )
