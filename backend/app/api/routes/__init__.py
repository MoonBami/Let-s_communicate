from fastapi import APIRouter

from app.api.routes import auth, complaints, dashboard

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(complaints.router)
api_router.include_router(dashboard.router)
