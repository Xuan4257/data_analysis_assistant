from app.services import report as report_service


def _report_inputs():
    eda = {
        "row_count": 20,
        "column_count": 3,
        "numeric_columns": ["feature_a", "feature_b", "target"],
        "categorical_columns": [],
        "numeric_stats": [
            {"column": "feature_a", "count": 20, "mean": 2.0, "std": 1.0, "min": 0.0, "median": 2.0, "max": 4.0},
            {"column": "target", "count": 20, "mean": 8.0, "std": 2.0, "min": 4.0, "median": 8.0, "max": 12.0},
        ],
        "categorical_stats": [],
        "correlation": {
            "columns": ["feature_a", "target"],
            "values": [[1.0, 0.8], [0.8, 1.0]],
        },
        "charts": [{"title": "目标变量分布", "kind": "distribution", "path": "charts/target.png"}],
    }
    regression = {
        "target_column": "target",
        "feature_columns": ["feature_a", "feature_b"],
        "sample_count": 20,
        "diagnostics": {
            "initial_model": {
                "name": "OLS",
                "r2": 0.82,
                "adjusted_r2": 0.79,
                "aic": 12.3,
                "bic": 14.2,
                "coefficients": [
                    {"feature": "const", "coefficient": 1.2},
                    {"feature": "feature_a", "coefficient": 2.5},
                    {"feature": "feature_b", "coefficient": -0.4},
                ],
            },
            "metrics": {
                "max_vif": 2.1,
                "shapiro_p": 0.4,
                "breusch_pagan_p": 0.3,
                "cooks_threshold": 0.2,
                "influential_points": 0,
            },
            "vif": [{"feature": "feature_a", "vif": 2.1}, {"feature": "feature_b", "vif": 1.9}],
            "recommendations": ["基础诊断未发现明显风险。"],
        },
        "diagnostic_charts": [{"title": "残差与拟合值", "path": "diagnostics/residuals.png"}],
        "comparison": [
            {"model": "Linear Regression", "rmse": 1.1, "mae": 0.8, "r2": 0.81, "adjusted_r2": 0.79, "aic": 10.1, "bic": 12.0, "parameters": 2},
            {"model": "Ridge", "rmse": 1.0, "mae": 0.7, "r2": 0.83, "adjusted_r2": 0.81, "aic": 9.8, "bic": 11.7, "parameters": 2},
        ],
        "best_model": {"model": "Ridge", "rmse": 1.0, "mae": 0.7, "r2": 0.83, "adjusted_r2": 0.81, "aic": 9.8, "bic": 11.7, "parameters": 2},
    }
    return eda, regression


def test_generate_report_has_fixed_sections_and_csv_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(report_service, "generate_report_insights", lambda summary: "- DeepSeek 补充解释。")
    eda, regression = _report_inputs()

    content = report_service.generate_report(
        tmp_path,
        "sample.csv",
        [{"action": "缺失值填补", "detail": "feature_a 使用中位数填补"}],
        eda,
        regression,
        proposal={"suggestions": [{"category": "缺失值", "title": "填补 feature_a", "detail": "检测到 1 个缺失值。"}]},
        cleaning_summary={"original_rows": 20, "cleaned_rows": 20, "original_columns": 3, "cleaned_columns": 3, "original_missing": 1, "cleaned_missing": 0},
    )

    headings = [f"## {index}. " for index in range(1, 11)]
    assert all(heading in content for heading in headings)
    assert "# 智能回归数据分析报告" in content
    assert "![目标变量分布](charts/target.png)" in content
    assert "![残差与拟合值](diagnostics/residuals.png)" in content
    assert "原始 JSON" not in content
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == content
    assert (tmp_path / "ols_coefficients.csv").is_file()
    assert (tmp_path / "vif_diagnostics.csv").is_file()

