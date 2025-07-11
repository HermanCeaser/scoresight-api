from fastapi import APIRouter
from .exams import router as exams_router

router = APIRouter()
router.include_router(exams_router, prefix="/exams", tags=["exams"])
