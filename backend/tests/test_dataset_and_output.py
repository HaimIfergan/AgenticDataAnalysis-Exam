from unittest.mock import patch

from fastapi.testclient import TestClient

from Pages.backend import PythonChatbot
from backend.agents import dataset_store
from backend.api.main import app


def test_compose_output_prefers_stdout_over_echo():
    query = "Quelles sont les colonnes ?"
    output = PythonChatbot._compose_output(
        query,
        messages=[],
        intermediate_outputs=[
            {
                "thought": f"Analyse demandée : {query}",
                "code": "print(list(df.columns))",
                "output": "['age', 'income']",
            }
        ],
    )
    assert "age" in output
    assert "Analyse demandée" not in output


def test_echo_pattern_is_rejected():
    assert PythonChatbot._is_echo_or_empty("Analyse demandée : hello", "hello")
    assert PythonChatbot._is_echo_or_empty("hello", "hello")
    assert not PythonChatbot._is_echo_or_empty("mean=42.5", "moyenne")


def test_dataset_survives_in_memory_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "UPLOAD_ROOT", str(tmp_path))
    dataset_store.clear_user(42)
    item = dataset_store.save_upload(42, "titanic.csv", b"age,sex\n22,m\n")
    assert item.variable_name == "df"
    dataset_store.clear_user(42)
    recovered = dataset_store.get_datasets(42)
    assert len(recovered) == 1
    assert recovered[0].data_path == item.data_path


def test_upload_then_ask_uses_persisted_dataset():
    client = TestClient(app)
    csv_bytes = b"age,income\n25,40000\n30,50000\n"

    upload = client.post(
        "/api/upload",
        data={"user_id": "7"},
        files={"file": ("demo.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["status"] == "ok"
    assert "age" in body["columns"]

    async def fake_ask(self, query: str, **kwargs):
        datasets = dataset_store.get_datasets(self.user_id)
        assert datasets, "le dataset uploadé doit être visible par l'agent"
        return {
            "status": "success",
            "output": "['age', 'income']",
            "fig": None,
            "figure": None,
        }

    with patch("backend.api.main.AgentManager.ask", new=fake_ask):
        response = client.post("/api/chat/ask", params={"user_id": 7, "query": "colonnes ?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["output"] == "['age', 'income']"
    assert "Analyse demandée" not in payload["output"]


def test_ask_accepts_file_in_same_request():
    client = TestClient(app)
    csv_bytes = b"col_a,col_b\n1,2\n"

    async def fake_ask(self, query: str, **kwargs):
        datasets = dataset_store.get_datasets(self.user_id)
        assert datasets
        return {"status": "success", "output": "ok-stdout", "fig": None}

    with patch("backend.api.main.AgentManager.ask", new=fake_ask):
        response = client.post(
            "/api/chat/ask",
            params={"user_id": 9, "query": "résume le fichier"},
            files={"file": ("inline.csv", csv_bytes, "text/csv")},
        )

    assert response.status_code == 200
    assert response.json()["output"] == "ok-stdout"
