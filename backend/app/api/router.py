"""Router raiz de la API. Cada fase engancha sus rutas aca."""

from fastapi import APIRouter

from app.api.routes import auth, health, meta, portfolio, transactions, users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(portfolio.router)
api_router.include_router(transactions.router)
