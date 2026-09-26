"""AlignerStudio FastAPI application (Phase 1 vertical slice)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.cases import router as cases_router

app = FastAPI(
    title="AlignerStudio API",
    version="0.1.0",
    description="Phase 1 vertical slice: case creation, STL upload, mesh validation, fixture plan.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-AlignerStudio-Manifest"],
)

app.include_router(cases_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
