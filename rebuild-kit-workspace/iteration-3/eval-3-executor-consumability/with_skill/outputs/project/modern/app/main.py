from starlette.requests import Request
from starlette.responses import Response

from fastapi import FastAPI

from app.api.tickets import router as tickets_router

# Byte-for-byte copy of Werkzeug's default production (debug=False) 500 page -- captured from
# a real legacy boot, see verification/replay/traces/legacy/tickets-create.jsonl
# (tickets-create-008-priority-invalid-LAST). Legacy has no error handling anywhere in
# app/server.py, so this exact page is what ANY uncaught exception in ANY legacy route
# produces; reproducing it via a single app-wide handler (rather than special-casing the one
# known trigger) matches that reality instead of just papering over one golden trace.
_WERKZEUG_500_PAGE = (
    "<!doctype html>\n"
    "<html lang=en>\n"
    "<title>500 Internal Server Error</title>\n"
    "<h1>Internal Server Error</h1>\n"
    "<p>The server encountered an internal error and was unable to complete your request. "
    "Either the server is overloaded or there is an error in the application.</p>\n"
)


def create_app() -> FastAPI:
    app = FastAPI(title="ticketd")
    app.include_router(tickets_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        return Response(
            content=_WERKZEUG_500_PAGE,
            status_code=500,
            media_type="text/html; charset=utf-8",
        )

    return app


app = create_app()
