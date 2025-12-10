from fastapi import APIRouter

from api.routes.agents.ai_sdk import router as ai_sdk_router
from api.routes.agents.chat import router as chat_router
from api.routes.agents.models import router as models_router

router = APIRouter(prefix="/agents")

router.include_router(chat_router)
router.include_router(models_router)
router.include_router(ai_sdk_router)
