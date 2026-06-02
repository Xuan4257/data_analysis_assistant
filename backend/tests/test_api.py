from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_status_connected(monkeypatch):
    monkeypatch.setattr(main, "test_connection", lambda: "连接成功")

    response = client.get("/api/config/status")

    assert response.status_code == 200
    assert response.json() == {"status": "connected", "message": "连接成功"}


def test_delete_task_removes_files_and_store_record(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "demo"
    task_dir.mkdir(parents=True)
    (task_dir / "input.csv").write_text("value\n1\n", encoding="utf-8")

    class Store:
        deleted = []

        def get(self, task_id):
            return {"id": task_id, "status": "completed", "task_dir": str(task_dir)}

        def delete(self, task_id):
            self.deleted.append(task_id)

    store = Store()
    monkeypatch.setattr(main, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(main, "store", store)

    response = client.delete("/api/tasks/demo")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "task_id": "demo"}
    assert store.deleted == ["demo"]
    assert not task_dir.exists()
