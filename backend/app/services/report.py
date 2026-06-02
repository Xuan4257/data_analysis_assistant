import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from .deepseek import generate_report_insights


TABLE_PREVIEW_ROWS = 10


def _display(value: Any, fallback: str = "未生成") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _cell(value: Any) -> str:
    return _display(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "未生成原因：没有可展示的数据。"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _write_csv(output_dir: Path, filename: str, headers: list[str], rows: list[list[Any]]) -> None:
    with (output_dir / filename).open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)


def _limited_names(values: list[str], limit: int = 12) -> str:
    if not values:
        return "无"
    visible = ", ".join(f"`{value}`" for value in values[:limit])
    hidden = len(values) - limit
    return f"{visible}，另有 {hidden} 项未展开" if hidden > 0 else visible


def _issue_lines(proposal: dict[str, Any]) -> str:
    suggestions = proposal.get("suggestions", [])
    if not suggestions:
        return "- 未检测到需要自动处理的数据质量问题。"
    lines = [
        f"- **{item.get('category', '数据问题')}**：{item.get('title', '未命名问题')}。{item.get('detail', '')}"
        for item in suggestions[:12]
    ]
    if len(suggestions) > 12:
        lines.append(f"- 其余 {len(suggestions) - 12} 项建议未在正文展开。")
    return "\n".join(lines)


def _cleaning_lines(cleaning_log: list[dict[str, Any]]) -> str:
    if not cleaning_log:
        return "- 未执行清洗操作。"
    lines = [f"- **{item.get('action', '清洗操作')}**：{item.get('detail', '无补充说明')}" for item in cleaning_log[:12]]
    if len(cleaning_log) > 12:
        lines.append(f"- 其余 {len(cleaning_log) - 12} 项操作未在正文展开。")
    return "\n".join(lines)


def _correlation_findings(eda: dict[str, Any]) -> str:
    correlation = eda.get("correlation", {})
    columns = correlation.get("columns", [])
    values = correlation.get("values", [])
    pairs: list[tuple[float, str, str, float]] = []
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            if column_index <= row_index or value is None:
                continue
            pairs.append((abs(float(value)), columns[row_index], columns[column_index], float(value)))
    if not pairs:
        return "- 未生成原因：数值型字段不足，无法计算变量间相关性。"
    pairs.sort(reverse=True)
    return "\n".join(
        f"- `{left}` 与 `{right}` 的相关系数为 **{value:.4f}**。"
        for _, left, right, value in pairs[:5]
    )


def _chart_explanation(chart: dict[str, str]) -> str:
    kind = chart.get("kind")
    if kind == "distribution":
        return "用于观察变量分布形态、偏态和潜在异常值。"
    if kind == "correlation":
        return "用于快速识别变量之间的线性相关方向和强度。"
    if kind == "scatter":
        return "用于观察特征与目标变量之间的关系形态。"
    if kind == "category":
        return "用于比较高频类别及其样本数量。"
    return "用于辅助解释回归诊断结果。"


def _chart_references(charts: list[dict[str, str]]) -> str:
    if not charts:
        return "- 未生成原因：没有可引用的图表文件。"
    lines = []
    for chart in charts:
        title = chart.get("title", "分析图表")
        path = chart.get("path", "")
        lines.extend([f"### {title}", _chart_explanation(chart), "", f"![{title}]({path})", ""])
    return "\n".join(lines).strip()


def _diagnostic_table(metrics: dict[str, Any]) -> str:
    max_vif = metrics.get("max_vif")
    shapiro_p = metrics.get("shapiro_p")
    breusch_pagan_p = metrics.get("breusch_pagan_p")
    influential_points = metrics.get("influential_points", 0)
    cooks_threshold = metrics.get("cooks_threshold")
    rows = [
        [
            "VIF 多重共线性",
            f"最大 VIF = {_display(max_vif)}",
            "是" if max_vif is not None and max_vif > 10 else "否",
            "VIF > 10 时重点比较 Ridge、LASSO 与 ElasticNet。" if max_vif is not None else "未生成原因：没有可计算 VIF 的特征组合。",
        ],
        [
            "残差正态性",
            f"Shapiro-Wilk p = {_display(shapiro_p)}",
            "是" if shapiro_p is not None and shapiro_p < 0.05 else "否",
            "p < 0.05 时结合 Q-Q 图，并比较稳健回归或目标变量变换。",
        ],
        [
            "异方差",
            f"Breusch-Pagan p = {_display(breusch_pagan_p)}",
            "是" if breusch_pagan_p is not None and breusch_pagan_p < 0.05 else "否",
            "p < 0.05 时结合 Scale-Location 图，考虑 WLS 或 Box-Cox 变换。",
        ],
        [
            "Cook's Distance 影响点",
            f"阈值 = {_display(cooks_threshold)}；强影响点 = {_display(influential_points)}",
            "是" if influential_points else "否",
            "存在强影响点时结合业务语义逐项复核，不应直接批量删除。",
        ],
    ]
    return _markdown_table(["诊断项", "指标结果", "是否存在问题", "触发的优化建议"], rows)


def _optimization_steps(regression: dict[str, Any]) -> str:
    metrics = regression["diagnostics"]["metrics"]
    features = regression["feature_columns"]
    steps = ["1. 首先建立 OLS 线性回归模型，作为可解释的基准模型。"]
    if metrics.get("max_vif") is not None and metrics["max_vif"] > 10:
        steps.append("2. 检测到 VIF 偏高，因此比较 Ridge、LASSO 与 ElasticNet，以降低共线性影响。")
    else:
        steps.append("2. 未检测到严重共线性；仍将 Ridge、LASSO 与 ElasticNet 作为正则化对照模型。")
    if metrics.get("shapiro_p") is not None and metrics["shapiro_p"] < 0.05:
        steps.append("3. 残差正态性检验未通过，因此加入 Huber 稳健回归进行比较。")
    else:
        steps.append("3. 加入 Huber 稳健回归作为异常扰动下的对照模型。")
    if len(features) <= 6:
        steps.append("4. 特征数量适中，因此加入二阶多项式回归，检查简单非线性关系。")
    else:
        steps.append("4. 特征数量较多，为控制参数规模，本次未加入二阶多项式回归。")
    steps.extend(
        [
            "5. 对所有成功训练的模型统一计算 RMSE、MAE、R²、Adjusted R²、AIC 和 BIC。",
            f"6. 以测试集 RMSE 为主要排序指标，选择 **{regression['best_model']['model']}** 作为当前最佳候选模型。",
        ]
    )
    return "\n".join(steps)


def _overfit_note(best: dict[str, Any], sample_count: int) -> str:
    parameters = best.get("parameters", 0)
    r2 = best.get("r2")
    adjusted_r2 = best.get("adjusted_r2")
    if parameters and sample_count and parameters / sample_count > 0.2:
        return "参数量相对于样本量较高，存在过拟合风险，建议增加交叉验证并扩大样本。"
    if r2 is not None and adjusted_r2 is not None and r2 - adjusted_r2 > 0.05:
        return "R² 与 Adjusted R² 差距较大，存在一定过拟合风险。"
    return "从当前参数规模及 Adjusted R² 看，未发现明显过拟合信号；仍建议使用独立验证集复核。"


def generate_report(
    output_dir: Path,
    filename: str,
    cleaning_log: list[dict[str, Any]],
    eda: dict[str, Any],
    regression: dict[str, Any],
    proposal: dict[str, Any] | None = None,
    cleaning_summary: dict[str, Any] | None = None,
) -> str:
    proposal = proposal or {}
    cleaning_summary = cleaning_summary or {}
    best = regression["best_model"]
    diagnostics = regression["diagnostics"]
    diagnostic_metrics = diagnostics["metrics"]
    initial_model = diagnostics["initial_model"]
    linear_result = next((row for row in regression["comparison"] if row.get("model") == "Linear Regression" and not row.get("error")), {})

    coefficient_rows = [
        [item.get("feature"), item.get("coefficient")]
        for item in initial_model.get("coefficients", [])
    ]
    vif_rows = [
        [item.get("feature"), item.get("vif")]
        for item in diagnostics.get("vif", [])
    ]
    _write_csv(output_dir, "ols_coefficients.csv", ["特征", "OLS 系数"], coefficient_rows)
    _write_csv(output_dir, "vif_diagnostics.csv", ["特征", "VIF"], vif_rows)

    comparison_rows = []
    for row in regression["comparison"]:
        if row.get("error"):
            comparison_rows.append([row["model"], "未生成", "未生成", "未生成", "未生成", "未生成", "未生成", "未生成原因：" + row["error"]])
        else:
            comparison_rows.append(
                [
                    row["model"],
                    row["rmse"],
                    row["mae"],
                    row["r2"],
                    row["adjusted_r2"],
                    row["aic"],
                    row["bic"],
                    row["parameters"],
                ]
            )

    numeric_stats_rows = [
        [row["column"], row["count"], row["mean"], row["std"], row["min"], row["median"], row["max"]]
        for row in eda.get("numeric_stats", [])[:TABLE_PREVIEW_ROWS]
    ]
    categorical_stats_rows = [
        [row["column"], row["unique"], row["top"], row["top_count"]]
        for row in eda.get("categorical_stats", [])[:TABLE_PREVIEW_ROWS]
    ]
    feature_contribution_rows = sorted(
        [row for row in coefficient_rows if row[0] != "const" and row[1] is not None],
        key=lambda row: abs(float(row[1])),
        reverse=True,
    )[:8]

    log_text = " ".join(item.get("action", "") for item in cleaning_log)
    before_rows = cleaning_summary.get("original_rows", eda["row_count"])
    after_rows = cleaning_summary.get("cleaned_rows", eda["row_count"])
    before_columns = cleaning_summary.get("original_columns", eda["column_count"])
    after_columns = cleaning_summary.get("cleaned_columns", eda["column_count"])
    before_missing = cleaning_summary.get("original_missing", "未生成")
    after_missing = cleaning_summary.get("cleaned_missing", "未生成")

    insight_summary = {
        "rows": eda["row_count"],
        "columns": eda["column_count"],
        "target": regression["target_column"],
        "best_model": best,
        "diagnostics": diagnostic_metrics,
        "numeric_stats": eda.get("numeric_stats", [])[:6],
    }
    ai_insights = generate_report_insights(insight_summary)
    if not ai_insights:
        ai_insights = (
            "- DeepSeek API 未启用或暂时不可用，本节使用本地统计结论。\n"
            f"- 当前最佳候选模型为 {best['model']}，测试集 RMSE 为 {best['rmse']}，R² 为 {best['r2']}。\n"
            "- 将模型用于正式决策前，应结合独立验证集和业务语义复核。"
        )

    all_charts = eda.get("charts", []) + regression.get("diagnostic_charts", [])
    chart_file_lines = "\n".join(f"- `{chart['path']}`：{chart['title']}" for chart in all_charts) or "- 未生成原因：没有图表文件。"
    output_files = [
        "cleaned_data.csv",
        "model_comparison.csv",
        "ols_coefficients.csv",
        "vif_diagnostics.csv",
        "analysis_summary.json",
        "report.md",
    ]

    report = f"""# 智能回归数据分析报告

> 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
> 数据文件：`{filename}`

## 1. 数据集概况

- 数据文件名：`{filename}`
- 数据规模：{eda["row_count"]} 行 × {eda["column_count"]} 列
- 目标变量：`{regression["target_column"]}`
- 特征变量：{_limited_names(regression["feature_columns"])}
- 字段类型概览：{len(eda.get("numeric_columns", []))} 个数值型字段，{len(eda.get("categorical_columns", []))} 个分类型字段
- 数值型字段：{_limited_names(eda.get("numeric_columns", []))}
- 分类型字段：{_limited_names(eda.get("categorical_columns", []))}
- 缺失值概况：清洗前共 {_display(before_missing)} 个，清洗后共 {_display(after_missing)} 个

## 2. 数据清洗摘要

### 原始问题列表

{_issue_lines(proposal)}

### 实际执行的清洗操作

{_cleaning_lines(cleaning_log)}

### 清洗前后变化

- 数据行数：{before_rows} → {after_rows}
- 字段数量：{before_columns} → {after_columns}
- 缺失值数量：{_display(before_missing)} → {_display(after_missing)}
- 是否删除重复行：{"是" if "移除重复" in log_text else "否"}
- 是否填补缺失值：{"是" if "缺失值填补" in log_text else "否"}
- 是否处理异常值：{"是" if "异常值缩尾" in log_text else "否"}

## 3. 探索性数据分析 EDA

### 数值型变量统计摘要

正文仅展示前 {TABLE_PREVIEW_ROWS} 个数值型字段的核心统计结果，避免堆叠大型表格。

{_markdown_table(["字段", "样本数", "均值", "标准差", "最小值", "中位数", "最大值"], numeric_stats_rows)}

### 分类型变量统计摘要

{_markdown_table(["字段", "唯一值数量", "最高频类别", "最高频次数"], categorical_stats_rows)}

### 主要相关性发现

{_correlation_findings(eda)}

### 图表列表与解释

{_chart_references(eda.get("charts", []))}

## 4. 初始线性回归结果

- 模型公式：`{regression["target_column"]} ~ {" + ".join(regression["feature_columns"])}`
- 基准模型：OLS 线性回归
- 说明：OLS 拟合优度来自完整有效样本；RMSE 和 MAE 来自测试集上的线性回归基准模型。

{_markdown_table(["指标", "结果"], [
    ["R²", initial_model.get("r2")],
    ["调整后 R²", initial_model.get("adjusted_r2")],
    ["RMSE", linear_result.get("rmse")],
    ["MAE", linear_result.get("mae")],
])}

### 回归系数表

正文仅展示前 {TABLE_PREVIEW_ROWS} 项，完整系数表请查看 `ols_coefficients.csv`。

{_markdown_table(["特征", "OLS 系数"], coefficient_rows[:TABLE_PREVIEW_ROWS])}

### 主要变量解释

{_markdown_table(["特征", "OLS 系数"], feature_contribution_rows)}

以上系数可用于识别相对重要的候选变量，但不能直接解释为因果效应。

### 显著性说明

未生成原因：当前回归模块未保留逐项 p 值和置信区间，因此本报告不对单个系数作显著性判断。

## 5. 回归诊断结果

{_diagnostic_table(diagnostic_metrics)}

VIF 明细正文仅展示前 {TABLE_PREVIEW_ROWS} 项，完整表格请查看 `vif_diagnostics.csv`。

{_markdown_table(["特征", "VIF"], vif_rows[:TABLE_PREVIEW_ROWS])}

### 诊断图

{_chart_references(regression.get("diagnostic_charts", []))}

## 6. 自动优化路径

{_optimization_steps(regression)}

## 7. 模型比较

{_markdown_table(["模型名称", "RMSE", "MAE", "R²", "Adjusted R²", "AIC", "BIC", "参数量"], comparison_rows)}

- 当前最佳模型：**{best["model"]}**
- 选择原因：在成功训练的候选模型中，**{best["model"]}** 的测试集 RMSE 最低，为 **{best["rmse"]}**。
- 过拟合风险：{_overfit_note(best, regression["sample_count"])}
- 完整模型比较表：`model_comparison.csv`

## 8. 最佳模型解释

- 最佳模型名称：**{best["model"]}**
- 关键特征贡献：当前最佳模型尚未统一输出特征重要性；可参考第 4 章的 OLS 系数排序，但不可将其视为所有模型的精确贡献。
- 模型适用边界：适用于与当前样本来源、字段定义和数值范围接近的数据。
- 不能过度解释的地方：预测关联不等于因果关系；异常点、数据漂移和样本偏差都可能改变模型表现。

## 9. 结论与建议

### 数据层面建议

- 复核强影响点和异常值处理策略，保留必要的业务解释记录。
- 新数据进入系统时，继续监控字段类型、缺失值比例和取值范围变化。

### 模型层面建议

- 使用独立验证集或交叉验证复核 **{best["model"]}** 的稳定性。
- 若残差诊断持续异常，可进一步评估 WLS、Box-Cox 或更适合业务机制的特征工程。

### 业务应用建议

- 将模型用于辅助判断，并为高影响决策保留人工复核环节。
- 对预测结果设置合理边界，不应外推到明显超出当前样本范围的数据。

### 后续改进方向

- 持续补充新样本，并对模型表现进行周期性复评。
- 结合业务定义补充可解释特征，减少仅依赖统计相关性的风险。

### DeepSeek 自然语言补充解释

{ai_insights}

## 10. 附录

### 生成的图表文件列表

{chart_file_lines}

### 输出文件列表

{chr(10).join(f"- `{filename}`" for filename in output_files)}

### 技术说明

- 数据清洗、EDA、回归训练和诊断均在本地执行。
- DeepSeek 仅接收聚合统计摘要，用于生成自然语言补充解释，不决定报告目录和统计结论。
- 大型结果表保存为 CSV 文件，Markdown 正文只保留核心摘要。
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    return report
