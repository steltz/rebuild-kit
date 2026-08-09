def test_export_csv_shape(client):
    # server.py:111-115 — id,title,status columns only, unauthenticated.
    client.post("/api/tickets", json={"title": "exported ticket"})
    r = client.get("/internal/export/csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "id,title,status"
    assert "exported ticket" in lines[1]
