"""Root API router — includes all sub-routers."""

from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.knowledge import router as knowledge_router
from app.api.chat import router as chat_router
from app.api.employees import router as employees_router
from app.api.expenses import router as expenses_router
from app.api.reimbursements import router as reimbursements_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(knowledge_router)
api_router.include_router(chat_router)
api_router.include_router(employees_router)
api_router.include_router(expenses_router)
api_router.include_router(reimbursements_router)
api_router.include_router(admin_router)


@api_router.get("/health")
def health_check():
    return {"status": "ok"}
