from fastapi import APIRouter

from app.api.routes import admin, auth, cases, complaints, dashboard, escalations, schools

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(complaints.router)
api_router.include_router(escalations.router)
api_router.include_router(cases.router)
api_router.include_router(dashboard.router)
api_router.include_router(schools.router)
api_router.include_router(admin.router)
