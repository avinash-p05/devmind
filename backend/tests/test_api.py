from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_document_contract() -> None:
    response = client.post(
        "/documents",
        json={
            "name": "oauth.md",
            "source_type": "document",
            "content": "Redirect validation happens before token exchange.",
            "metadata": {"path": "docs/oauth.md"},
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "oauth.md"
    assert response.json()["content_length"] > 0

    listing = client.get("/documents")
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
