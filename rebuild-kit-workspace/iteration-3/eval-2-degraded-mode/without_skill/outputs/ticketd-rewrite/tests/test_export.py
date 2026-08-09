import pytest


@pytest.mark.asyncio
async def test_export_csv(client):
    await client.post("/api/tickets", json={"title": "exportable"})

    resp = await client.get("/internal/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.splitlines()
    assert lines[0] == "id,title,status"
    assert any("exportable" in line for line in lines[1:])
