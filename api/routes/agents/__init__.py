from fastapi import APIRouter
from routes.agents.admin import router as admin_router
from routes.agents.chat import router as chat_router
from routes.agents.models import router as models_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(models_router)
router.include_router(admin_router)
