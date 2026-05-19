"""
main.py - FastAPI Application Entry Point
All routes are defined in app/api/routes.py
"""
from fastapi import FastAPI, Form, Request, Response, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote, unquote
import uvicorn
import traceback as tb_module
import os, uuid, datetime, re
import qrcode, io

from app.core.auth import get_current_user, can_bypass_dept, is_global_admin, require_login, can_see_all_molds
from app.services.db_service import verify_user

app = FastAPI()

from app.core.templates import templates

# ââ Upload directory ââââââââââââââââââââââââââââââââââ
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads", "nominations")
os.makedirs(UPLOADS_DIR, exist_ok=True)

if os.path.exists(UPLOADS_DIR):
    app.mount("/uploads/nominations", StaticFiles(directory=UPLOADS_DIR), name="nom_uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ââ Global exception handler ââââââââââââââââââââââââââ
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    err_text = traceback.format_exc()
    import logging
    logging.getLogger(__name__).error("[GLOBAL EXCEPTION] %s\n%s", exc, err_text)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": str(exc), "data": None}
    )

# ââ Import all routes (modular) âââââââââââââââââââââââââââââââââ
from app.api import routes
from app.api import tech, prod, sales, materials, qc, pkg, spray, admin, qa, prod_sessions
from app.api import prod_api, tech_api, qa_api, pkg_api

app.include_router(routes.router)        # åºç¡è·¯ç±ï¼login/logout/dashboard/...)
app.include_router(tech.mold_router)     # /tooling /molds /cavity_review â?æ¨¡å·å°è´¦ï¼æ åç¼ï¼?
app.include_router(tech.router)          # /tech/*
app.include_router(tech.sample_router)    # /api/sample-tasks/*  â?ææ ·ä¸?PPAP å®å
app.include_router(tech.molds_api_router)  # /api/molds/*  â?æ¨¡å· JSON API
app.include_router(tech.maintenance_router) # /tech/maintenance/* â?åè½¨ç»´ä¿®
app.include_router(prod.router)           # /prod/*
app.include_router(prod_sessions.router)  # /prod/sessions/* â?çäº§ä¼è¯é»å£å­?
app.include_router(sales.api_router)     # /api/* â?AJAX æ¥å£ï¼å¿é¡»å¨ /sales ä¹åï¼?
app.include_router(sales.router)          # /sales/*
app.include_router(materials.router)          # /materials/*
app.include_router(materials.material_api_router)  # /api/materials/* â?QR èµç  JSON API
app.include_router(qc.router)            # /qc/*
app.include_router(qa.router)            # /qa/* â?åè´¨ä¸å®¡è®?
app.include_router(pkg.router)           # /pkg/* ¡ª °ü×°Ò³ÃæÂ·ÓÉ
app.include_router(pkg_api.router)       # /pkg/* ¡ª °ü×° JSON API£¨Èë¿â + ½á°¸£©
app.include_router(tech_api.router)      # /tech/* ¡ª ´òÑùÓëÔ´Í·½¨µµ JSON API
app.include_router(spray.router)          # /spray/*
app.include_router(admin.router)          # /machines /audit

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
