from pathlib import Path

import pandas as pd


def load_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "gbk"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV 编码无法识别，请使用 UTF-8 或 GBK 编码")
    if suffix in {".xls", ".xlsx"}:
        return pd.read_excel(path)
    if suffix == ".json":
        try:
            return pd.read_json(path)
        except ValueError:
            return pd.read_json(path, lines=True)
    raise ValueError(f"不支持的文件格式：{suffix}")


def dataframe_preview(frame: pd.DataFrame, rows: int = 8) -> list[dict]:
    preview = frame.head(rows).copy()
    preview = preview.where(pd.notna(preview), None)
    return preview.to_dict(orient="records")

