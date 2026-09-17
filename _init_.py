from aiogram import Router
from .user import router as user_router
from .admin import router as admin_router
from .payment import router as payment_router
from .referral import router as referral_router

def setup_routers() -> Router:
    router = Router()
    router.include_router(user_router)
    router.include_router(admin_router)
    router.include_router(payment_router)
    router.include_router(referral_router)
    return router
