from fastapi import APIRouter

from api.routes.agents.chat import router as chat_router
from api.routes.agents.models import router as models_router
from api.routes.agents.threads import router as threads_router

router = APIRouter()

router.include_router(chat_router, prefix="/agents")
router.include_router(models_router, prefix="/agents")
router.include_router(threads_router, prefix="/agents")
