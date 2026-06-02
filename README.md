# Insight Forge 智能数据分析台

一个本地运行的数据分析工作台：上传 CSV、Excel 或 JSON 文件，确认清洗建议和回归变量后，系统会完成 EDA、OLS 诊断、自适应模型比较和 Markdown 报告生成。

## 技术栈

- 前端：React、Vite、ECharts
- 后端：FastAPI、pandas、scikit-learn、statsmodels
- 环境：Conda `smart-data-analysis`
- 模型增强：兼容 OpenAI Chat Completions 协议的 API，可在页面中配置

已配置的 API 只接收聚合统计摘要，用于增强报告洞察。数据清洗、EDA 和回归分析在本地执行；未配置 API 时也可完成全部分析步骤。

## 安装

```powershell
conda create -n smart-data-analysis python=3.11 -y
conda run -n smart-data-analysis pip install -r backend/requirements.txt
cd frontend
npm install
```

## 启动

打开两个 PowerShell 窗口：

```powershell
.\scripts\start_backend.ps1
```

```powershell
.\scripts\start_frontend.ps1
```

浏览器访问 `http://127.0.0.1:5173`。首次使用时可进入“API 配置”页面填写 Base URL、API Key 和模型名称。

## 分析输出

每次任务的结果位于 `backend/data/tasks/<task-id>/output/`，也可从页面下载 ZIP 压缩包：

- `cleaned_data.csv`
- `charts/*.png`
- `diagnostics/*.png`
- `model_comparison.csv`
- `analysis_summary.json`
- `report.md`

## 测试

```powershell
conda run -n smart-data-analysis pytest -q backend/tests
```
