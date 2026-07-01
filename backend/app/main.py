"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
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

# CORS — allow Vue dev server in Phase 8
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "service": "Expense Reimbursement AI Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.env == "development",
    )
