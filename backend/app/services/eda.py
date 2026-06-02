from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _clean_number(value: Any) -> float | None:
    if pd.isna(value) or np.isinf(value):
        return None
    return round(float(value), 6)


def _save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def run_eda(frame: pd.DataFrame, output_dir: Path, target_column: str) -> dict[str, Any]:
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    numeric_columns = list(frame.select_dtypes(include=np.number).columns)
    categorical_columns = [column for column in frame.columns if column not in numeric_columns]
    charts: list[dict[str, str]] = []

    for index, column in enumerate(numeric_columns[:8]):
        plt.figure(figsize=(6.4, 3.8))
        sns.histplot(frame[column].dropna(), bins=24, kde=True, color="#e66b3d")
        plt.title(f"Distribution: {column}")
        plt.xlabel(column)
        path = charts_dir / f"numeric_distribution_{index + 1}.png"
        _save_figure(path)
        charts.append({"title": f"{column} 分布", "kind": "distribution", "path": f"charts/{path.name}"})

    correlation_payload: dict[str, Any] = {"columns": [], "values": []}
    if len(numeric_columns) >= 2:
        correlation = frame[numeric_columns[:16]].corr().fillna(0)
        plt.figure(figsize=(max(6, len(correlation) * 0.58), max(4.5, len(correlation) * 0.46)))
        sns.heatmap(correlation, cmap="vlag", center=0, square=True)
        plt.title("Correlation matrix")
        path = charts_dir / "correlation_heatmap.png"
        _save_figure(path)
        charts.append({"title": "相关性矩阵", "kind": "correlation", "path": f"charts/{path.name}"})
        correlation_payload = {
            "columns": list(correlation.columns),
            "values": [
                [_clean_number(value) for value in row]
                for row in correlation.to_numpy()
            ],
        }

    if target_column in numeric_columns:
        feature_columns = [column for column in numeric_columns if column != target_column]
        for index, column in enumerate(feature_columns[:4]):
            plt.figure(figsize=(6.4, 3.8))
            sns.scatterplot(data=frame, x=column, y=target_column, alpha=0.62, color="#35676f")
            plt.title(f"{target_column} vs {column}")
            path = charts_dir / f"target_scatter_{index + 1}.png"
            _save_figure(path)
            charts.append({"title": f"{target_column} 与 {column}", "kind": "scatter", "path": f"charts/{path.name}"})

    for index, column in enumerate(categorical_columns[:4]):
        counts = frame[column].fillna("空值").astype(str).value_counts().head(12)
        plt.figure(figsize=(6.4, 3.8))
        sns.barplot(x=counts.values, y=counts.index, color="#d8ad52")
        plt.title(f"Top categories: {column}")
        path = charts_dir / f"category_count_{index + 1}.png"
        _save_figure(path)
        charts.append({"title": f"{column} 高频类别", "kind": "category", "path": f"charts/{path.name}"})

    numeric_stats = []
    if numeric_columns:
        stats = frame[numeric_columns].describe().T
        for column, row in stats.iterrows():
            numeric_stats.append(
                {
                    "column": column,
                    "count": int(row["count"]),
                    "mean": _clean_number(row["mean"]),
                    "std": _clean_number(row["std"]),
                    "min": _clean_number(row["min"]),
                    "median": _clean_number(row["50%"]),
                    "max": _clean_number(row["max"]),
                }
            )

    categorical_stats = []
    for column in categorical_columns[:12]:
        counts = frame[column].fillna("空值").astype(str).value_counts()
        categorical_stats.append(
            {
                "column": column,
                "unique": int(frame[column].nunique(dropna=True)),
                "top": counts.index[0] if not counts.empty else "",
                "top_count": int(counts.iloc[0]) if not counts.empty else 0,
            }
        )

    return {
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "numeric_stats": numeric_stats,
        "categorical_stats": categorical_stats,
        "correlation": correlation_payload,
        "charts": charts,
    }

