from .auth import auth_router
from .users import users_router
from .inquiries import inquiries_router
from .websocket import websocket_router

__all__ = [
    "auth_router",
    "users_router",
    "inquiries_router",
    "websocket_router",
]
