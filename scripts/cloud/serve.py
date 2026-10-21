"""Windows test deployment: serve the built Vue app and existing API together."""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def write_managed_state(port):
    """Record the actual worker identity for the Windows start/stop launcher."""
    import ctypes
    from ctypes import wintypes
    import json
    import os

    if os.name != "nt":
        raise RuntimeError("Managed task mode requires Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(kernel_time), ctypes.byref(user_time)):
        raise ctypes.WinError(ctypes.get_last_error())
    # FILETIME starts at 1601; System.DateTime ticks start at year 1.
    ticks = ((created.dwHighDateTime << 32) | created.dwLowDateTime) + 504911232000000000
    runtime = PROJECT_ROOT / "logs" / "cloud-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    temporary = runtime / "server.json.tmp"
    temporary.write_text(json.dumps({"pid": os.getpid(), "startedUtcTicks": str(ticks), "port": port}), encoding="utf-8")
    temporary.replace(runtime / "server.json")


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
    parser.add_argument("--managed", action="store_true")
    args = parser.parse_args()
    if args.managed:
        write_managed_state(args.port)
    uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)
