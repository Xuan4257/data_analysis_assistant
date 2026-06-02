from pathlib import Path
from typing import Any
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNetCV, HuberRegressor, LassoCV, LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures, StandardScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor


def _number(value: Any) -> float | None:
    value = float(value)
    return round(value, 6) if np.isfinite(value) else None


def _build_preprocessor(frame: pd.DataFrame) -> ColumnTransformer:
    numeric = list(frame.select_dtypes(include=np.number).columns)
    categorical = [column for column in frame.columns if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "category",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encode",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                                max_categories=20,
                            ),
                        ),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers=transformers, remainder="drop")


def _pipeline(frame: pd.DataFrame, estimator: Any, polynomial_degree: int | None = None) -> Pipeline:
    steps: list[tuple[str, Any]] = [("prepare", _build_preprocessor(frame))]
    if polynomial_degree:
        steps.append(("polynomial", PolynomialFeatures(degree=polynomial_degree, include_bias=False)))
    steps.append(("model", estimator))
    return Pipeline(steps)


def _evaluate(name: str, model: Pipeline, x_train: pd.DataFrame, x_test: pd.DataFrame, y_train: pd.Series, y_test: pd.Series) -> tuple[dict[str, Any], np.ndarray]:
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    sample_count = len(y_test)
    parameter_count = max(1, len(model.named_steps["model"].coef_.ravel()) if hasattr(model.named_steps["model"], "coef_") else x_train.shape[1])
    rss = max(float(np.sum((y_test.to_numpy() - predicted) ** 2)), 1e-12)
    r2 = float(r2_score(y_test, predicted))
    adjusted_denominator = sample_count - parameter_count - 1
    adjusted_r2 = 1 - (1 - r2) * (sample_count - 1) / adjusted_denominator if adjusted_denominator > 0 else r2
    return (
        {
            "model": name,
            "rmse": _number(np.sqrt(mean_squared_error(y_test, predicted))),
            "mae": _number(mean_absolute_error(y_test, predicted)),
            "r2": _number(r2),
            "adjusted_r2": _number(adjusted_r2),
            "aic": _number(sample_count * np.log(rss / sample_count) + 2 * parameter_count),
            "bic": _number(sample_count * np.log(rss / sample_count) + parameter_count * np.log(sample_count)),
            "parameters": int(parameter_count),
        },
        predicted,
    )


def _save_diagnostics(output_dir: Path, fitted: np.ndarray, residuals: np.ndarray) -> list[dict[str, str]]:
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    charts: list[dict[str, str]] = []
    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(6.4, 3.8))
    sns.scatterplot(x=fitted, y=residuals, color="#35676f", alpha=0.65)
    plt.axhline(0, color="#e66b3d", linewidth=1.2)
    plt.xlabel("Fitted values")
    plt.ylabel("Residuals")
    plt.title("Residuals vs fitted")
    path = diagnostics_dir / "residuals_vs_fitted.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    charts.append({"title": "残差与拟合值", "path": f"diagnostics/{path.name}"})

    plt.figure(figsize=(6.4, 3.8))
    sm.qqplot(residuals, line="45", fit=True, ax=plt.gca())
    plt.title("Normal Q-Q")
    path = diagnostics_dir / "qq_plot.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    charts.append({"title": "残差 Q-Q 图", "path": f"diagnostics/{path.name}"})

    plt.figure(figsize=(6.4, 3.8))
    sns.scatterplot(x=fitted, y=np.sqrt(np.abs(residuals)), color="#d8ad52", alpha=0.65)
    plt.xlabel("Fitted values")
    plt.ylabel("Sqrt(|residuals|)")
    plt.title("Scale-location")
    path = diagnostics_dir / "scale_location.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    charts.append({"title": "Scale-Location 图", "path": f"diagnostics/{path.name}"})
    return charts


def _ols_diagnostics(x: pd.DataFrame, y: pd.Series, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    processor = _build_preprocessor(x)
    encoded = np.asarray(processor.fit_transform(x), dtype=float)
    feature_names = list(processor.get_feature_names_out())
    encoded_constant = sm.add_constant(encoded, has_constant="add")
    model = sm.OLS(y.to_numpy(dtype=float), encoded_constant).fit()
    fitted = np.asarray(model.fittedvalues)
    residuals = np.asarray(model.resid)
    influence = model.get_influence()
    cooks = np.asarray(influence.cooks_distance[0])

    vif_rows = []
    if encoded.shape[1] > 1:
        for index, name in enumerate(feature_names[:40]):
            try:
                value = variance_inflation_factor(encoded, index)
            except Exception:
                value = np.nan
            vif_rows.append({"feature": name, "vif": _number(value)})
    finite_vifs = [row["vif"] for row in vif_rows if row["vif"] is not None]
    max_vif = max(finite_vifs, default=0.0)

    sample = residuals[: min(5000, len(residuals))]
    shapiro_p = stats.shapiro(sample).pvalue if len(sample) >= 3 else np.nan
    try:
        breusch_pagan_p = het_breuschpagan(residuals, encoded_constant)[1]
    except Exception:
        breusch_pagan_p = np.nan
    cooks_threshold = 4 / max(len(y), 1)
    influential_count = int((cooks > cooks_threshold).sum())

    recommendations = []
    if max_vif > 10:
        recommendations.append("检测到较高多重共线性，加入 Ridge、LASSO 与 ElasticNet 进行比较。")
    if np.isfinite(shapiro_p) and shapiro_p < 0.05:
        recommendations.append("残差正态性检验未通过，加入稳健回归并建议检查目标变量变换。")
    if np.isfinite(breusch_pagan_p) and breusch_pagan_p < 0.05:
        recommendations.append("检测到异方差，建议结合 Scale-Location 图考虑 WLS 或 Box-Cox 变换。")
    if influential_count:
        recommendations.append(f"检测到 {influential_count} 个强影响点，请结合业务语义复核。")
    if not recommendations:
        recommendations.append("基础诊断未发现明显风险，仍将比较正则化和非线性候选模型。")

    coefficients = [
        {"feature": "const" if index == 0 else feature_names[index - 1], "coefficient": _number(value)}
        for index, value in enumerate(model.params[:41])
    ]
    return (
        {
            "initial_model": {
                "name": "OLS",
                "r2": _number(model.rsquared),
                "adjusted_r2": _number(model.rsquared_adj),
                "aic": _number(model.aic),
                "bic": _number(model.bic),
                "coefficients": coefficients,
            },
            "metrics": {
                "max_vif": _number(max_vif),
                "shapiro_p": _number(shapiro_p),
                "breusch_pagan_p": _number(breusch_pagan_p),
                "cooks_threshold": _number(cooks_threshold),
                "influential_points": influential_count,
            },
            "vif": vif_rows,
            "recommendations": recommendations,
        },
        _save_diagnostics(output_dir, fitted, residuals),
    )


def run_regression(frame: pd.DataFrame, output_dir: Path, target_column: str, feature_columns: list[str]) -> dict[str, Any]:
    if target_column not in frame.columns:
        raise ValueError(f"目标列不存在：{target_column}")
    selected_features = [column for column in feature_columns if column in frame.columns and column != target_column]
    if not selected_features:
        selected_features = [column for column in frame.columns if column != target_column]
    if not selected_features:
        raise ValueError("至少需要选择一个特征列")

    working = frame[selected_features + [target_column]].copy()
    working[target_column] = pd.to_numeric(working[target_column], errors="coerce")
    working = working.dropna(subset=[target_column])
    if len(working) < 12:
        raise ValueError("有效数据少于 12 行，无法进行可靠的回归分析")

    x = working[selected_features]
    y = working[target_column]
    diagnostics, diagnostic_charts = _ols_diagnostics(x, y, output_dir)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.22, random_state=42)
    cv = min(5, max(2, len(x_train) // 6))

    candidates: list[tuple[str, Pipeline]] = [
        ("Linear Regression", _pipeline(x, LinearRegression())),
        ("Ridge", _pipeline(x, RidgeCV(alphas=np.logspace(-3, 3, 30)))),
        ("LASSO", _pipeline(x, LassoCV(alphas=np.logspace(-4, 1, 36), cv=cv, max_iter=8000))),
        (
            "ElasticNet",
            _pipeline(x, ElasticNetCV(l1_ratio=[0.15, 0.5, 0.85], alphas=np.logspace(-4, 1, 28), cv=cv, max_iter=8000)),
        ),
        ("Huber Robust", _pipeline(x, HuberRegressor(max_iter=800))),
    ]
    if len(selected_features) <= 6:
        candidates.append(("Polynomial Degree 2", _pipeline(x, LinearRegression(), polynomial_degree=2)))

    comparisons: list[dict[str, Any]] = []
    prediction_map: dict[str, np.ndarray] = {}
    fitted_models: dict[str, Pipeline] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, candidate in candidates:
            try:
                metrics, prediction = _evaluate(name, candidate, x_train, x_test, y_train, y_test)
                comparisons.append(metrics)
                prediction_map[name] = prediction
                fitted_models[name] = candidate
            except Exception as exc:
                comparisons.append({"model": name, "error": str(exc)})

    successful = [row for row in comparisons if row.get("rmse") is not None]
    if not successful:
        raise ValueError("所有候选模型均训练失败，请检查目标列和特征列")
    successful.sort(key=lambda row: row["rmse"])
    best = successful[0]
    best_prediction = prediction_map[best["model"]]
    comparisons_frame = pd.DataFrame(comparisons)
    comparisons_frame.to_csv(output_dir / "model_comparison.csv", index=False, encoding="utf-8-sig")

    preview_count = min(240, len(y_test))
    prediction_chart = [
        {"actual": _number(actual), "predicted": _number(predicted)}
        for actual, predicted in zip(y_test.iloc[:preview_count], best_prediction[:preview_count])
    ]
    return {
        "target_column": target_column,
        "feature_columns": selected_features,
        "sample_count": int(len(working)),
        "diagnostics": diagnostics,
        "diagnostic_charts": diagnostic_charts,
        "comparison": comparisons,
        "best_model": best,
        "prediction_chart": prediction_chart,
    }

