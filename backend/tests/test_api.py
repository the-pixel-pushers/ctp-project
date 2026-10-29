import uuid

from app.config import get_settings
from tests.conftest import blurry_image, encode, sharp_image

URL = "/api/v1/cull-batch"


def test_mixed_batch_isolates_failures(client):
    files = [
        ("files", ("sharp.png", encode(sharp_image(), ".png"), "image/png")),
        ("files", ("blurry.jpg", encode(blurry_image(), ".jpg"), "image/jpeg")),
        ("files", ("corrupt.jpg", b"\xff\xd8\xff garbage", "image/jpeg")),
        ("files", ("notes.txt", b"hello", "text/plain")),
    ]
    resp = client.post(URL, files=files)
    assert resp.status_code == 200
    body = resp.json()

    uuid.UUID(body["batch_id"])
    assert body["total_processed"] == 4
    results = body["results"]
    assert [r["filename"] for r in results] == ["sharp.png", "blurry.jpg", "corrupt.jpg", "notes.txt"]

    sharp, blurry, corrupt, txt = results
    assert sharp["status"] == "success" and sharp["error"] is None
    assert sharp["analyses"]["blur"]["flag"] == "ACCEPTABLE"

    blur = blurry["analyses"]["blur"]
    assert blur["status"] == "success" and blur["flag"] == "BLURRY"
    assert 0.0 <= blur["score"] <= 1.0
    assert "laplacian_variance" in blur["metrics"]

    for failed in (corrupt, txt):
        assert failed["status"] == "error"
        assert failed["error"]
        assert failed["analyses"] == {}


def test_missing_files_rejected(client):
    assert client.post(URL).status_code == 422


def test_batch_size_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_files_per_batch", 1)
    png = encode(sharp_image(64, 64), ".png")
    files = [("files", (f"{i}.png", png, "image/png")) for i in range(2)]
    assert client.post(URL, files=files).status_code == 413


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
