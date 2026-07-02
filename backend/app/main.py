"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Ensure data directories exist
    os.makedirs(settings.storage.invoice_storage_path, exist_ok=True)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title="Expense Reimbursement AI Agent",
    description="Enterprise-grade AI Agent for expense reimbursement — ReAct Agent with Cloud Brain, Local Hands",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Serve uploaded invoice/attachment files via a simple route instead of
# StaticFiles mount, so we can handle path variations robustly.
# URLs like /api/v1/files/filename.ext and /api/v1/files/invoices/filename.ext
# both resolve to ./data/invoices/<basename>.
@app.get("/api/v1/files/{filename:path}")
def serve_invoice_file(filename: str):
    """Serve uploaded invoice/attachment files.

    Extracts just the base filename so paths like
    ``invoices/abc.jpg``, ``data/invoices/abc.jpg``,
    or ``abc.jpg`` all resolve to ``./data/invoices/abc.jpg``.
    """
    safe_name = os.path.basename(filename)
    file_path = os.path.join(settings.storage.invoice_storage_path, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {safe_name}")
    return FileResponse(file_path)


@app.get("/")
def root():
    return {
        "service": "Expense Reimbursement AI Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }