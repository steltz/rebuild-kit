from fastapi import FastAPI

app = FastAPI(title="ticketd")


@app.get("/healthz")
async def healthz():
    return {"ok": True}
