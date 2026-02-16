from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.main import api_router
from app.core.cache import init_redis, close_redis
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging, db_handler
from app.core.middleware import RequestLoggingMiddleware

# Configure logging before anything else
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    if db_handler:
        await db_handler.start()
    yield
    if db_handler:
        await db_handler.stop()
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)
