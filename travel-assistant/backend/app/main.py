from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import ROOT, settings
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="国内单城市 AI 行程规划、地图、预算与导出",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")


@app.get("/")
async def root():
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {
            "app": settings.app_name,
            "status": "backend-only",
            "message": "前端尚未构建。开发模式请运行 frontend 的 pnpm dev，或执行 pnpm build。",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    )


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if DIST.exists():
        candidate = DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
