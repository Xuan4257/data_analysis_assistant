import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd


def _safe_name(value: Any) -> str:
    name = str(value).strip().lower()
    name = re.sub(r"[\s\-/\\]+", "_", name)
    name = re.sub(r"[^\w\u4e00-\u9fff]+", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "column"


def normalized_columns(columns: list[Any]) -> list[str]:
    seen: Counter[str] = Counter()
    result: list[str] = []
    for column in columns:
        base = _safe_name(column)
        seen[base] += 1
        result.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return result


def _numeric_conversion_ratio(series: pd.Series) -> float:
    non_empty = series.dropna().astype(str).str.strip()
    if non_empty.empty:
        return 0.0
    converted = pd.to_numeric(non_empty.str.replace(",", "", regex=False), errors="coerce")
    return float(converted.notna().mean())


def build_cleaning_proposal(frame: pd.DataFrame) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    renamed = normalized_columns(list(frame.columns))
    if list(frame.columns) != renamed:
        suggestions.append(
            {
                "id": "normalize_columns",
                "category": "列名规范化",
                "title": "统一列名格式",
                "detail": "去除多余空格和符号，将重复列名自动编号，便于后续建模。",
                "affected": len(frame.columns),
                "recommended": True,
            }
        )

    duplicate_count = int(frame.duplicated().sum())
    if duplicate_count:
        suggestions.append(
            {
                "id": "drop_duplicates",
                "category": "重复记录",
                "title": "移除完全重复的数据行",
                "detail": f"检测到 {duplicate_count} 行完全重复记录。",
                "affected": duplicate_count,
                "recommended": True,
            }
        )

    for column in frame.columns:
        series = frame[column]
        missing = int(series.isna().sum())
        if missing:
            strategy = "中位数" if pd.api.types.is_numeric_dtype(series) else "众数"
            suggestions.append(
                {
                    "id": f"fill_missing::{column}",
                    "category": "缺失值",
                    "title": f"填补 {column} 的缺失值",
                    "detail": f"检测到 {missing} 个缺失值，建议使用{strategy}填补。",
                    "affected": missing,
                    "recommended": True,
                }
            )

        if series.dtype == "object":
            ratio = _numeric_conversion_ratio(series)
            if ratio >= 0.85:
                suggestions.append(
                    {
                        "id": f"convert_numeric::{column}",
                        "category": "类型转换",
                        "title": f"将 {column} 转换为数值",
                        "detail": f"{ratio:.0%} 的非空值可解析为数值。",
                        "affected": int(series.notna().sum()),
                        "recommended": True,
                    }
                )

        if pd.api.types.is_numeric_dtype(series) and series.notna().sum() >= 8:
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            if pd.notna(iqr) and iqr > 0:
                outliers = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
                if outliers:
                    suggestions.append(
                        {
                            "id": f"cap_outliers::{column}",
                            "category": "异常值",
                            "title": f"缩尾处理 {column} 的异常值",
                            "detail": f"检测到 {outliers} 个 IQR 异常值，将限制到上下界。",
                            "affected": outliers,
                            "recommended": False,
                        }
                    )

    columns = [
        {
            "name": str(column),
            "dtype": str(frame[column].dtype),
            "missing": int(frame[column].isna().sum()),
            "unique": int(frame[column].nunique(dropna=True)),
            "numeric": bool(pd.api.types.is_numeric_dtype(frame[column])),
        }
        for column in frame.columns
    ]
    numeric_columns = [item["name"] for item in columns if item["numeric"]]
    recommended_target = numeric_columns[-1] if numeric_columns else ""
    return {
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": columns,
        "suggestions": suggestions,
        "recommended_target": recommended_target,
        "recommended_features": [column for column in numeric_columns if column != recommended_target],
    }


def apply_cleaning(frame: pd.DataFrame, accepted_ids: list[str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cleaned = frame.copy()
    log: list[dict[str, Any]] = []
    accepted = set(accepted_ids)

    if "normalize_columns" in accepted:
        before = list(cleaned.columns)
        cleaned.columns = normalized_columns(before)
        log.append({"action": "列名规范化", "detail": f"{before} -> {list(cleaned.columns)}"})

    if "drop_duplicates" in accepted:
        before = len(cleaned)
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        log.append({"action": "移除重复行", "detail": f"移除 {before - len(cleaned)} 行"})

    # Suggestions retain original column names. Resolve them after optional normalization.
    original_to_current = dict(zip(frame.columns, normalized_columns(list(frame.columns))))
    for suggestion_id in accepted:
        if "::" not in suggestion_id:
            continue
        operation, original_column = suggestion_id.split("::", 1)
        column = original_to_current.get(original_column, original_column) if "normalize_columns" in accepted else original_column
        if column not in cleaned.columns:
            continue
        series = cleaned[column]
        if operation == "convert_numeric":
            cleaned[column] = pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")
            log.append({"action": "类型转换", "detail": f"{column} 转换为数值列"})
        elif operation == "fill_missing":
            if pd.api.types.is_numeric_dtype(series):
                value = series.median()
            else:
                modes = series.mode(dropna=True)
                value = modes.iloc[0] if not modes.empty else "未知"
            cleaned[column] = series.fillna(value)
            log.append({"action": "缺失值填补", "detail": f"{column} 使用 {value} 填补"})
        elif operation == "cap_outliers" and pd.api.types.is_numeric_dtype(series):
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            cleaned[column] = series.clip(lower=lower, upper=upper)
            log.append({"action": "异常值缩尾", "detail": f"{column} 限制到 [{lower:.4g}, {upper:.4g}]"})

    cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
    return cleaned, log

