import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts";
import { api } from "./api";

const STATUS_LABELS = {
  awaiting_confirmation: "待确认",
  queued: "排队中",
  running: "分析中",
  completed: "已完成",
  failed: "失败",
};

function Icon({ name, size = 18 }) {
  const paths = {
    upload: "M12 16V4m0 0L7 9m5-5 5 5M5 20h14",
    flask: "M9 3h6m-1 0v5l5.2 8.7A2.2 2.2 0 0 1 17.3 20H6.7a2.2 2.2 0 0 1-1.9-3.3L10 8V3",
    settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7.4-3.5.1-1.4 2-1.5-2-3.4-2.3.9a7.7 7.7 0 0 0-2.4-1.4L14.5 2h-5L9 4.7a7.7 7.7 0 0 0-2.3 1.4l-2.4-.9-2 3.4 2.1 1.6-.1 1.4.1 1.4-2.1 1.6 2 3.4 2.4-.9A7.7 7.7 0 0 0 9 19.3l.5 2.7h5l.5-2.7a7.7 7.7 0 0 0 2.3-1.4l2.4.9 2-3.4-2.1-1.6.1-1.4-.3-.4Z",
    home: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1Z",
    database: "M4 6c0 1.7 3.6 3 8 3s8-1.3 8-3-3.6-3-8-3-8 1.3-8 3Zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
    folder: "M3 6.5h6l2 2h10v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z",
    box: "m12 3 8 4.5v9L12 21l-8-4.5v-9Zm0 9 8-4.5M12 12 4 7.5M12 12v9",
    book: "M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2Zm0 0v14M8 7h7",
    bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 20a2 2 0 0 0 4 0",
    clock: "M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    trash: "M4 7h16M10 11v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3",
    arrow: "M5 12h13m-5-5 5 5-5 5",
    check: "m5 12 4 4L19 6",
    download: "M12 4v11m0 0 4-4m-4 4-4-4M5 20h14",
    expand: "M8 3H3v5m13-5h5v5M8 21H3v-5m18 0v5h-5",
    close: "M18 6 6 18M6 6l12 12",
    file: "M14 2H6a2 2 0 0 0-2 2v16h16V8Zm0 0v6h6",
    chart: "M4 19V5m0 14h16M8 16v-5m4 5V7m4 9v-3",
    refresh: "M20 11a8.1 8.1 0 0 0-15.5-3M4 5v3h3m-3 5a8.1 8.1 0 0 0 15.5 3m.5 3v-3h-3",
    key: "M15 7a4 4 0 1 1-7.5 2H3v4h3v3h3v-3h2.5A4 4 0 0 1 15 7Z",
    sparkle: "m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8ZM19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7Z",
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name] || paths.sparkle} />
    </svg>
  );
}

function Chart({ option, className = "" }) {
  const container = useRef(null);
  useEffect(() => {
    if (!container.current) return undefined;
    const chart = echarts.init(container.current);
    chart.setOption(option);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [option]);
  return <div className={`echart ${className}`} ref={container} />;
}

function Metric({ label, value, note }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

function Shell({ view, setView, tasks, apiStatus, onDeleteTask, children }) {
  const navItems = [
    ["workflow", "home", "分析工作台"],
    ["settings", "settings", "API 配置"],
    ["workflow", "database", "数据管理"],
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">DS</div>
          <div><strong>数据分析助手</strong><span>智能数据分析平台</span></div>
        </div>
        <nav>
          {navItems.map(([target, icon, label]) => (
            <button className={view === target ? "active" : ""} key={target} onClick={() => setView(target)}>
              <Icon name={icon} /> {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-model">
          <div className={`api-status ${apiStatus.status}`}>
            <span>模型状态</span>
            <b>{apiStatus.status === "checking" ? "检测中..." : apiStatus.status === "connected" ? "连接成功" : "连接失败"}</b>
          </div>
          <dl>
            <div><dt>当前模型</dt><dd>可配置</dd></div>
            <div><dt>API 服务</dt><dd>{apiStatus.status === "connected" ? "已连接" : "待连接"}</dd></div>
            <div><dt>今日任务</dt><dd>{tasks.length} 次</dd></div>
          </dl>
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}

function Settings({ config, setConfig, notify, refreshApiStatus }) {
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const save = async ({ checkStatus = true } = {}) => {
    setSaving(true);
    try {
      const next = await api.saveConfig(config);
      setConfig({ ...next, api_key: "" });
      notify("API 配置已保存", "success");
      if (checkStatus) refreshApiStatus();
      return true;
    } catch (error) {
      notify(error.message, "error");
      return false;
    } finally {
      setSaving(false);
    }
  };
  const test = async () => {
    setTesting(true);
    try {
      if (!await save({ checkStatus: false })) return;
      const result = await api.testConfig();
      notify(result.message || "API 连接成功", "success");
      refreshApiStatus();
    } catch (error) {
      notify(error.message, "error");
      refreshApiStatus();
    } finally {
      setTesting(false);
    }
  };
  return (
    <section className="page settings-page">
      <header className="page-heading">
        <span className="eyebrow">MODEL CONNECTION / SETTINGS</span>
        <h1>API 配置</h1>
        <p>支持兼容 OpenAI Chat Completions 协议的 API。接口仅用于增强报告洞察，统计计算与回归建模始终在本地完成。</p>
      </header>
      <div className="settings-grid">
        <div className="config-card">
          <div className="section-title"><span>01</span><h2>接口参数</h2></div>
          <label>API Base URL<input placeholder="例如：https://api.openai.com/v1" value={config.base_url || ""} onChange={(event) => setConfig({ ...config, base_url: event.target.value })} /></label>
          <label>API Key<input type="password" placeholder={config.has_api_key ? "已保存密钥，留空则保持不变" : "sk-..."} value={config.api_key || ""} onChange={(event) => setConfig({ ...config, api_key: event.target.value })} /></label>
          <label>模型名称<input placeholder="例如：gpt-4o-mini、deepseek-chat" value={config.model || ""} onChange={(event) => setConfig({ ...config, model: event.target.value })} /></label>
          <label className="toggle-row">
            <span><b>启用智能洞察</b><small>关闭后报告将使用本地统计摘要</small></span>
            <input type="checkbox" checked={config.enabled ?? true} onChange={(event) => setConfig({ ...config, enabled: event.target.checked })} />
          </label>
          <div className="actions">
            <button className="button secondary" onClick={save} disabled={saving}>{saving ? "保存中..." : "保存配置"}</button>
            <button className="button primary" onClick={test} disabled={testing}><Icon name="key" /> {testing ? "测试中..." : "保存并测试连接"}</button>
          </div>
        </div>
        <aside className="note-card">
          <span className="eyebrow">PRIVACY NOTE</span>
          <h3>数据留在本机</h3>
          <p>系统向你配置的 API 发送聚合统计摘要，不会上传原始数据行。密钥保存在后端本地配置文件中。</p>
          <div className="line" />
          <small>兼容示例</small>
          <code>OpenAI / DeepSeek / 兼容网关</code>
        </aside>
      </div>
    </section>
  );
}

function DashboardStat({ icon, label, value, note, tone }) {
  return (
    <div className="dashboard-stat">
      <span className={`stat-icon ${tone}`}><Icon name={icon} /></span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        <em>{note}</em>
      </div>
    </div>
  );
}

function MiniLineChart() {
  return (
    <svg className="mini-chart" viewBox="0 0 420 210" role="img" aria-label="输出趋势示意图">
      <defs>
        <linearGradient id="lineFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#2f7df6" stopOpacity=".22" />
          <stop offset="100%" stopColor="#2f7df6" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[40, 80, 120, 160].map((y) => <line key={y} x1="28" x2="398" y1={y} y2={y} />)}
      <polyline points="28,178 78,132 128,102 178,118 228,88 278,48 328,70 378,44" />
      <polygon points="28,178 78,132 128,102 178,118 228,88 278,48 328,70 378,44 378,190 28,190" />
      {[[28,178], [78,132], [128,102], [178,118], [228,88], [278,48], [328,70], [378,44]].map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="5" />)}
      <text x="28" y="206">1月</text><text x="128" y="206">2月</text><text x="228" y="206">4月</text><text x="360" y="206">6月</text>
    </svg>
  );
}

function UploadPanel({ onUpload, busy, tasks, apiStatus, onDeleteTask, setView }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const choose = (file) => file && onUpload(file);
  const completed = tasks.filter((item) => item.status === "completed").length;
  const active = tasks.filter((item) => ["queued", "running"].includes(item.status)).length;
  const latest = tasks.slice(0, 5);
  return (
    <section className="dashboard-page">
      <header className="dashboard-top">
        <div>
          <h1>欢迎回来，数据分析师</h1>
          <p>今天是 2026年6月9日，准备好探索你的数据了吗？</p>
        </div>
      </header>

      <div className="dashboard-stats">
        <DashboardStat icon="database" label="数据集" value={tasks.length || 0} note="本地任务记录" tone="blue" />
        <DashboardStat icon="chart" label="分析任务" value={tasks.length || 0} note={`运行中 ${active}`} tone="green" />
        <DashboardStat icon="file" label="完成报告" value={completed} note="可下载报告" tone="purple" />
        <DashboardStat icon="clock" label="运行中" value={active} note={apiStatus.status === "connected" ? "API 已连接" : "API 待配置"} tone="orange" />
      </div>

      <div className="dashboard-main-grid">
        <div className={`dashboard-upload ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]); }}>
          <input ref={input} type="file" accept=".csv,.xlsx,.xls,.json" onChange={(event) => choose(event.target.files[0])} />
          <div className="upload-orb"><Icon name="upload" size={34} /></div>
          <div><b>{busy ? "正在读取数据..." : "拖拽文件到这里，或 "}<button onClick={() => input.current?.click()} disabled={busy}>点击上传</button></b><span>支持 CSV、Excel、JSON 文件，最大 50 MB</span></div>
          <small>数据仅用于分析，不会被存储用于模型训练</small>
        </div>

        <aside className="quick-card">
          <h2>快速开始</h2>
          <button onClick={() => input.current?.click()}><span className="quick-icon blue"><Icon name="file" /></span><b>新建分析项目</b><small>从上传数据开始分析</small><i>+</i></button>
          <button><span className="quick-icon green"><Icon name="database" /></span><b>导入示例数据</b><small>使用内置示例数据集</small><i>⌁</i></button>
          <button onClick={() => setView("settings")}><span className="quick-icon mint"><Icon name="key" /></span><b>使用 API 分析</b><small>通过 API 提交数据分析</small><i>↗</i></button>
        </aside>
      </div>

      <section className="workflow-card">
        <h2>分析流程</h2>
        {["数据上传", "数据清洗", "探索分析", "建模分析", "生成报告"].map((label, index) => (
          <div className={index === 0 ? "active" : ""} key={label}><span>{index + 1}</span><b>{label}</b><small>{["导入数据文件", "处理缺失值与异常", "EDA 可视化分析", "回归与预测分析", "输出分析报告"][index]}</small></div>
        ))}
      </section>

      <div className="dashboard-bottom-grid">
        <section className="panel-card dataset-card">
          <header><h2>最近数据集</h2><button>查看全部 <Icon name="arrow" size={14} /></button></header>
          <table>
            <thead><tr><th>文件名</th><th>状态</th><th>更新时间</th><th></th></tr></thead>
            <tbody>
              {latest.length === 0 && <tr><td colSpan="4">还没有分析记录</td></tr>}
              {latest.map((item) => (
                <tr key={item.id}>
                  <td><span className="file-pill">{item.filename.split(".").pop()?.toUpperCase() || "DATA"}</span>{item.filename}</td>
                  <td><span className={`status-badge ${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span></td>
                  <td>{new Date(item.updated_at || item.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
                  <td><button className="table-delete" onClick={() => onDeleteTask(item)}><Icon name="trash" size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="panel-card pipeline-card">
          <header><h2>分析流水线状态</h2><button>查看全部 <Icon name="arrow" size={14} /></button></header>
          {(latest.length ? latest : [{ id: "empty", filename: "暂无任务", status: "awaiting_confirmation", progress: 0 }]).slice(0, 4).map((item) => (
            <div className="pipeline-row" key={item.id}>
              <span className={`pipeline-dot ${item.status}`}><Icon name={item.status === "completed" ? "check" : item.status === "failed" ? "close" : "chart"} size={14} /></span>
              <div><b>{item.filename}</b><small>{STATUS_LABELS[item.status] || "待开始"} · {item.progress || 0}%</small><i style={{ width: `${item.progress || 0}%` }} /></div>
            </div>
          ))}
        </section>

        <section className="panel-card preview-card">
          <header><h2>输出预览</h2><button>查看全部 <Icon name="arrow" size={14} /></button></header>
          <div className="preview-tabs"><span className="active">图表示例</span><span>表格预览</span><span>报告预览</span></div>
          <h3>数据趋势分析（示例）</h3>
          <MiniLineChart />
        </section>
      </div>
    </section>
  );
}

function Proposal({ task, onAnalyze, busy }) {
  const proposal = task.proposal;
  const [selected, setSelected] = useState(() => new Set(proposal.suggestions.filter((item) => item.recommended).map((item) => item.id)));
  const [target, setTarget] = useState(proposal.recommended_target || "");
  const [features, setFeatures] = useState(() => new Set(proposal.recommended_features || []));
  const toggle = (setState, value) => setState((current) => {
    const next = new Set(current);
    next.has(value) ? next.delete(value) : next.add(value);
    return next;
  });
  const allSuggestionsSelected = proposal.suggestions.length > 0 && selected.size === proposal.suggestions.length;
  const toggleAllSuggestions = () => {
    setSelected(allSuggestionsSelected ? new Set() : new Set(proposal.suggestions.map((item) => item.id)));
  };
  const submit = () => onAnalyze({
    accepted_suggestion_ids: [...selected],
    target_column: target,
    feature_columns: [...features],
  });
  return (
    <section className="page">
      <header className="page-heading compact">
        <span className="eyebrow">CLEANING REVIEW / {task.id}</span>
        <h1>确认清洗方案</h1>
        <p>系统只会执行你勾选的操作。异常值缩尾默认需要人工确认。</p>
      </header>
      <div className="metrics-row">
        <Metric label="数据行数" value={proposal.row_count.toLocaleString()} />
        <Metric label="字段数量" value={proposal.column_count} />
        <Metric label="清洗建议" value={proposal.suggestions.length} />
        <Metric label="当前状态" value="待确认" note={task.filename} />
      </div>
      <div className="review-layout">
        <div>
          <div className="section-title">
            <span>01</span><h2>清洗建议</h2>
            <div className="selection-tools">
              <small>{selected.size} 项已选择</small>
              <label className="select-all">
                <input type="checkbox" checked={allSuggestionsSelected} onChange={toggleAllSuggestions} disabled={proposal.suggestions.length === 0} />
                <span className="select-all-box"><Icon name="check" size={12} /></span>
                全选
              </label>
            </div>
          </div>
          <div className="suggestion-list">
            {proposal.suggestions.length === 0 && <div className="empty-small">数据质量良好，没有自动清洗建议。</div>}
            {proposal.suggestions.map((item) => (
              <label className={`suggestion ${selected.has(item.id) ? "checked" : ""}`} key={item.id}>
                <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggle(setSelected, item.id)} />
                <span className="checkmark"><Icon name="check" size={15} /></span>
                <span><b>{item.title}</b><small>{item.detail}</small></span>
                <em>{item.category}</em>
              </label>
            ))}
          </div>
          <div className="section-title table-title"><span>02</span><h2>数据预览</h2></div>
          <div className="table-wrap">
            <table><thead><tr>{proposal.columns.map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead>
              <tbody>{task.preview.map((row, index) => <tr key={index}>{proposal.columns.map((column) => <td key={column.name}>{String(row[column.name] ?? "—")}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
        <aside className="variable-panel">
          <div className="section-title"><span>03</span><h2>回归变量</h2></div>
          <label className="field-label">目标列<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">请选择目标列</option>{proposal.columns.map((column) => <option key={column.name}>{column.name}</option>)}</select></label>
          <p className="field-label">特征列</p>
          <div className="feature-list">
            {proposal.columns.filter((column) => column.name !== target).map((column) => (
              <label key={column.name}><input type="checkbox" checked={features.has(column.name)} onChange={() => toggle(setFeatures, column.name)} /><span>{column.name}</span><small>{column.dtype}</small></label>
            ))}
          </div>
          <button className="button primary full" disabled={!target || features.size === 0 || busy} onClick={submit}><Icon name="arrow" /> {busy ? "正在提交..." : "确认并开始分析"}</button>
        </aside>
      </div>
    </section>
  );
}

function Progress({ task, refresh }) {
  const stages = ["应用清洗方案", "生成 EDA 图表", "OLS 诊断", "自适应模型比较", "生成报告"];
  return (
    <section className="progress-page">
      <span className="eyebrow">ANALYSIS IN PROGRESS / {task.id}</span>
      <h1>{task.stage}</h1>
      <p>后台任务正在本地运行，页面会自动更新进度。</p>
      <div className="progress-rail"><i style={{ width: `${task.progress}%` }} /></div>
      <strong className="progress-number">{task.progress}<small>%</small></strong>
      <div className="stage-grid">
        {stages.map((stage, index) => <div className={task.progress >= [12, 32, 58, 72, 82][index] ? "done" : ""} key={stage}><span>0{index + 1}</span><b>{stage}</b></div>)}
      </div>
      <button className="button secondary" onClick={refresh}><Icon name="refresh" /> 手动刷新</button>
    </section>
  );
}

function ArtifactGallery({ task, charts }) {
  return <div className="gallery">{charts.map((chart) => <figure key={chart.path}><img src={api.fileUrl(task.id, chart.path)} alt={chart.title} loading="lazy" /><figcaption>{chart.title}</figcaption></figure>)}</div>;
}

function ReportViewer({ task }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api.report(task.id)
      .then((next) => active && setReport(next))
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [task.id]);
  return (
    <div className={`report-card ${fullscreen ? "report-fullscreen" : ""}`}>
      <div className="report-toolbar">
        <div className="report-title"><Icon name="file" size={26} /><span className="eyebrow">MARKDOWN REPORT</span></div>
        <div className="report-actions">
          <button className="button secondary" onClick={() => setFullscreen(!fullscreen)}><Icon name={fullscreen ? "close" : "expand"} /> {fullscreen ? "退出全屏" : "展开全屏查看"}</button>
          <a className="button secondary" href={api.reportDownloadUrl(task.id)}><Icon name="download" /> 下载完整报告</a>
        </div>
      </div>
      {loading && <p className="report-state">正在读取报告...</p>}
      {error && <p className="report-state error">报告读取失败：{error}</p>}
      {!loading && !error && <pre>{report?.content || "报告内容为空。"}</pre>}
    </div>
  );
}

function Results({ task }) {
  const [tab, setTab] = useState("overview");
  const result = task.result;
  const eda = result.eda;
  const regression = result.regression;
  const successful = regression.comparison.filter((item) => !item.error);
  const heatmapOption = useMemo(() => ({
    tooltip: { position: "top" },
    grid: { left: 85, right: 22, top: 20, bottom: 75 },
    xAxis: { type: "category", data: eda.correlation.columns, axisLabel: { rotate: 40, color: "#c3cedb" } },
    yAxis: { type: "category", data: eda.correlation.columns, axisLabel: { color: "#c3cedb" } },
    visualMap: { min: -1, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 2, inRange: { color: ["#315f93", "#f8fafc", "#3b82f6"] }, textStyle: { color: "#c3cedb" } },
    series: [{ type: "heatmap", data: eda.correlation.values.flatMap((row, y) => row.map((value, x) => [x, y, value])), emphasis: { itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.45)" } } }],
  }), [eda]);
  const comparisonOption = useMemo(() => ({
    tooltip: { trigger: "axis" },
    grid: { left: 55, right: 20, top: 25, bottom: 65 },
    xAxis: { type: "category", data: successful.map((item) => item.model), axisLabel: { rotate: 18, color: "#c3cedb" } },
    yAxis: { type: "value", name: "RMSE", axisLabel: { color: "#c3cedb" }, splitLine: { lineStyle: { color: "rgba(195,206,219,.14)" } } },
    series: [{ type: "bar", data: successful.map((item) => item.rmse), itemStyle: { color: "#3b82f6", borderRadius: [3, 3, 0, 0] } }],
  }), [successful]);
  const predictionOption = useMemo(() => ({
    tooltip: { trigger: "item" },
    grid: { left: 60, right: 20, top: 25, bottom: 45 },
    xAxis: { type: "value", name: "实际值", axisLabel: { color: "#c3cedb" }, splitLine: { lineStyle: { color: "rgba(195,206,219,.14)" } } },
    yAxis: { type: "value", name: "预测值", axisLabel: { color: "#c3cedb" }, splitLine: { lineStyle: { color: "rgba(195,206,219,.14)" } } },
    series: [{ type: "scatter", symbolSize: 9, data: regression.prediction_chart.map((item) => [item.actual, item.predicted]), itemStyle: { color: "#93c5fd" } }],
  }), [regression]);
  return (
    <section className="page results-page">
      <header className="results-head">
        <div><span className="eyebrow">ANALYSIS COMPLETE / {task.id}</span><h1>分析结果</h1><p>{task.filename} · {eda.row_count.toLocaleString()} 行数据</p></div>
        <a className="button primary" href={api.downloadUrl(task.id)}><Icon name="download" /> 下载完整结果包</a>
      </header>
      <div className="tabbar">
        {["overview", "eda", "models", "report"].map((name) => <button className={tab === name ? "active" : ""} key={name} onClick={() => setTab(name)}>{({ overview: "总览", eda: "EDA 图表", models: "模型诊断", report: "分析报告" })[name]}</button>)}
      </div>
      {tab === "overview" && <div>
        <div className="metrics-row">
          <Metric label="最佳模型" value={regression.best_model.model} />
          <Metric label="测试集 RMSE" value={regression.best_model.rmse} />
          <Metric label="测试集 R²" value={regression.best_model.r2} />
          <Metric label="强影响点" value={regression.diagnostics.metrics.influential_points} />
        </div>
        <div className="result-grid"><div className="chart-card"><h3>模型预测表现</h3><Chart option={predictionOption} /></div><div className="insight-card"><span className="eyebrow">DIAGNOSTIC NOTES</span><h3>诊断路径</h3>{regression.diagnostics.recommendations.map((item) => <p key={item}>{item}</p>)}</div></div>
      </div>}
      {tab === "eda" && <div>
        {eda.correlation.columns.length > 1 && <div className="chart-card wide"><h3>相关性矩阵</h3><Chart option={heatmapOption} className="heatmap" /></div>}
        <ArtifactGallery task={task} charts={eda.charts} />
      </div>}
      {tab === "models" && <div>
        <div className="chart-card wide"><h3>候选模型 RMSE 对比</h3><Chart option={comparisonOption} /></div>
        <div className="table-wrap result-table"><table><thead><tr><th>模型</th><th>RMSE</th><th>MAE</th><th>R²</th><th>Adjusted R²</th><th>AIC</th></tr></thead><tbody>{regression.comparison.map((row) => <tr key={row.model}><td>{row.model}</td>{row.error ? <td colSpan="5">{row.error}</td> : <><td>{row.rmse}</td><td>{row.mae}</td><td>{row.r2}</td><td>{row.adjusted_r2}</td><td>{row.aic}</td></>}</tr>)}</tbody></table></div>
        <ArtifactGallery task={task} charts={regression.diagnostic_charts} />
      </div>}
      {tab === "report" && <ReportViewer task={task} />}
    </section>
  );
}

function App() {
  const [view, setView] = useState("workflow");
  const [tasks, setTasks] = useState([]);
  const [task, setTask] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [apiStatus, setApiStatus] = useState({ status: "checking", message: "正在检测 API 连接" });
  const [config, setConfig] = useState({ base_url: "", model: "", enabled: true, api_key: "" });
  const notify = (message, type = "info") => { setNotice({ message, type }); setTimeout(() => setNotice(null), 4200); };
  const refreshTasks = () => api.tasks().then(setTasks).catch(() => {});
  const refreshApiStatus = () => {
    setApiStatus({ status: "checking", message: "正在检测 API 连接" });
    return api.configStatus()
      .then(setApiStatus)
      .catch((error) => setApiStatus({ status: "failed", message: error.message }));
  };
  const refreshTask = async (id = task?.id) => {
    if (!id) return;
    try {
      const next = await api.task(id);
      setTask(next);
      refreshTasks();
    } catch (error) {
      notify(error.message, "error");
    }
  };
  useEffect(() => {
    api.config().then((data) => setConfig({ ...data, api_key: "" })).catch(() => {});
    refreshTasks();
    refreshApiStatus();
  }, []);
  useEffect(() => {
    if (view.startsWith("task:")) {
      const id = view.split(":")[1];
      refreshTask(id);
      setView("workflow");
    }
  }, [view]);
  useEffect(() => {
    if (!task || !["queued", "running"].includes(task.status)) return undefined;
    const timer = setInterval(() => refreshTask(task.id), 1100);
    return () => clearInterval(timer);
  }, [task?.id, task?.status]);
  const upload = async (file) => {
    setBusy(true);
    try {
      const next = await api.upload(file);
      setTask(next);
      refreshTasks();
      notify("文件解析完成，请确认清洗方案", "success");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const analyze = async (payload) => {
    setBusy(true);
    try {
      const next = await api.analyze(task.id, payload);
      setTask(next);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const deleteTask = async (targetTask) => {
    if (!window.confirm(`确定删除“${targetTask.filename}”这份数据分析吗？删除后无法恢复。`)) return;
    try {
      await api.deleteTask(targetTask.id);
      if (task?.id === targetTask.id) setTask(null);
      await refreshTasks();
      notify("任务已删除", "success");
    } catch (error) {
      notify(error.message, "error");
    }
  };
  let content;
  if (view === "settings") content = <Settings config={config} setConfig={setConfig} notify={notify} refreshApiStatus={refreshApiStatus} />;
  else if (!task) content = <UploadPanel onUpload={upload} busy={busy} tasks={tasks} apiStatus={apiStatus} onDeleteTask={deleteTask} setView={setView} />;
  else if (task.status === "awaiting_confirmation") content = <Proposal task={task} onAnalyze={analyze} busy={busy} />;
  else if (["queued", "running"].includes(task.status)) content = <Progress task={task} refresh={() => refreshTask()} />;
  else if (task.status === "completed") content = <Results task={task} />;
  else content = <section className="progress-page"><span className="eyebrow">ANALYSIS FAILED</span><h1>分析没有完成</h1><p>{task.error}</p><button className="button secondary" onClick={() => setTask(null)}>重新上传数据</button></section>;
  return <Shell view={view} setView={setView} tasks={tasks} apiStatus={apiStatus} onDeleteTask={deleteTask}>{content}{notice && <div className={`notice ${notice.type}`}>{notice.message}</div>}</Shell>;
}

export default App;
