from api.routes.accounts import router as accounts_router
from api.routes.agents import router as agents_router
from api.routes.uploads import router as uploads_router

__all__ = ["accounts_router", "agents_router", "uploads_router"]
