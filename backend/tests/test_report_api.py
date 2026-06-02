from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_report_preview_full_and_download(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    full_content = "# 智能回归数据分析报告\n\n## 1. 数据集概况\n\n摘要\n\n## 5. 回归诊断结果\n\n完整内容"
    (output_dir / "report.md").write_text(full_content, encoding="utf-8")
    monkeypatch.setattr(
        main,
        "_get_task_or_404",
        lambda task_id: {"id": task_id, "status": "completed", "task_dir": str(tmp_path)},
    )

    preview = client.get("/api/tasks/demo/report/preview")
    assert preview.status_code == 200
    assert preview.json()["is_preview"] is True
    assert "## 5. 回归诊断结果" not in preview.json()["content"]

    full = client.get("/api/tasks/demo/report")
    assert full.status_code == 200
    assert full.json()["content"] == full_content
    assert full.json()["is_preview"] is False

    download = client.get("/api/tasks/demo/report/download")
    assert download.status_code == 200
    assert download.content == (output_dir / "report.md").read_bytes()
