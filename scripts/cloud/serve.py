"""Windows test deployment: serve the built Vue app and existing API together."""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def create_app():
    from fastapi.responses import FileResponse
    from starlette.exceptions import HTTPException
    from starlette.routing import Route
    from starlette.staticfiles import StaticFiles

    from main import app

    dist = PROJECT_ROOT / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError("Frontend build missing. Run start-cloud.cmd first.")

    class VueFiles(StaticFiles):
        async def get_response(self, path, scope):
            # Missing API calls and attachments must retain their 404 responses.
            reserved = {"api", "uploads", "static", "health", "docs", "redoc", "openapi.json"}
            # StaticFiles normalizes URL paths with os.path on Windows.
            first = path.replace("\\", "/").lstrip("/").split("/", 1)[0]
            if first in reserved:
                raise HTTPException(status_code=404)
            try:
                response = await super().get_response(path, scope)
            except HTTPException as error:
                accept = dict(scope.get("headers", [])).get(b"accept", b"")
                if (error.status_code != 404 or scope["method"] not in {"GET", "HEAD"}
                        or Path(path).suffix or ".." in Path(path).parts
                        or b"text/html" not in accept):
                    raise
                response = FileResponse(index)
            if response.media_type == "text/html":
                response.headers["Cache-Control"] = "no-cache"
            return response

    async def homepage(request):
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    # Only this deployment entry point overrides the JSON landing page.
    # All API routes, attachments and the original lifespan remain unchanged.
    app.router.routes.insert(0, Route("/", homepage, methods=["GET", "HEAD"]))
    app.mount("/", VueFiles(directory=dist, html=True), name="cloud-frontend")
    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)
