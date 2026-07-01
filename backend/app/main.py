"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def root():
    return {
        "service": "Expense Reimbursement AI Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }