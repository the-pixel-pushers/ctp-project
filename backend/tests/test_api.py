import uuid

from app.config import get_settings
from tests.conftest import blurry_image, encode, sharp_image, solid_image

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
    assert sharp["analyses"]["blur"]["flag"] == "SHARP"

    blur = blurry["analyses"]["blur"]
    assert blur["status"] == "success" and blur["flag"] == "BLURRY"
    assert 0.0 <= blur["score"] <= 1.0
    assert "laplacian_variance" in blur["metrics"]

    for failed in (corrupt, txt):
        assert failed["status"] == "error"
        assert failed["error"]
        assert failed["analyses"] == {}


def test_every_analyzer_runs_on_every_image(client):
    files = [
        ("files", ("white.png", encode(solid_image(255), ".png"), "image/png")),
        ("files", ("black.png", encode(solid_image(0), ".png"), "image/png")),
        ("files", ("sharp.png", encode(sharp_image(), ".png"), "image/png")),
    ]
    results = client.post(URL, files=files).json()["results"]

    for result in results:
        assert set(result["analyses"]) == {"blur", "overexposure", "underexposure"}
        for analysis in result["analyses"].values():
            assert analysis["status"] == "success"
            assert 0.0 <= analysis["score"] <= 1.0

    white, black, sharp = (r["analyses"] for r in results)
    assert white["overexposure"]["flag"] == "OVEREXPOSED"
    assert white["underexposure"]["flag"] == "OK"
    assert black["underexposure"]["flag"] == "UNDEREXPOSED"
    assert black["overexposure"]["flag"] == "OK"
    assert sharp["overexposure"]["flag"] == "OK"


def test_missing_files_rejected(client):
    assert client.post(URL).status_code == 422


def test_batch_size_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_files_per_batch", 1)
    png = encode(sharp_image(64, 64), ".png")
    files = [("files", (f"{i}.png", png, "image/png")) for i in range(2)]
    assert client.post(URL, files=files).status_code == 413


def test_client_ids_round_trip_with_duplicate_filenames(client):
    files = [
        ("files", ("a.png", encode(sharp_image(), ".png"), "image/png")),
        ("files", ("a.png", encode(blurry_image(), ".png"), "image/png")),
        ("files", ("corrupt.jpg", b"\xff\xd8\xff garbage", "image/jpeg")),
        ("files", ("notes.txt", b"hello", "text/plain")),
    ]
    ids = ["id-0", "id-1", "id-2", "id-3"]
    resp = client.post(URL, files=files, data={"client_ids": ids})
    assert resp.status_code == 200
    results = resp.json()["results"]

    assert [r["index"] for r in results] == [0, 1, 2, 3]
    assert [r["client_id"] for r in results] == ids
    assert results[0]["analyses"]["blur"]["flag"] == "SHARP"
    assert results[1]["analyses"]["blur"]["flag"] == "BLURRY"
    assert results[2]["status"] == "error" and results[3]["status"] == "error"


def test_client_ids_optional(client):
    files = [("files", (f"{i}.png", encode(sharp_image(64, 64), ".png"), "image/png")) for i in range(2)]
    results = client.post(URL, files=files).json()["results"]
    assert [r["index"] for r in results] == [0, 1]
    assert all(r["client_id"] is None for r in results)


def test_client_ids_length_mismatch_rejected(client):
    files = [("files", (f"{i}.png", encode(sharp_image(64, 64), ".png"), "image/png")) for i in range(2)]
    assert client.post(URL, files=files, data={"client_ids": ["only-one"]}).status_code == 422


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
