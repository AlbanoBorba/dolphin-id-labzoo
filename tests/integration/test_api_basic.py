from fastapi.testclient import TestClient

def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_list_sessions_empty(client: TestClient):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json() == []

def test_create_session_validation_error(client: TestClient):
    # Missing parameters should throw 422
    response = client.post("/api/sessions", json={})
    assert response.status_code == 422
