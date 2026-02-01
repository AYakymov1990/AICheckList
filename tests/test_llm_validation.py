from fastapi.testclient import TestClient

from app.main import app


def test_llm_smoke_rejects_long_prompt() -> None:
    client = TestClient(app)
    long_prompt = "x" * 2001
    response = client.post("/llm/smoke", json={"prompt": long_prompt})
    assert response.status_code == 422
