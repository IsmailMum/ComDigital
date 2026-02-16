import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

logger = logging.getLogger(__name__)

engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.is_superuser == True)
        )
        superuser = result.scalars().first()

        if not superuser:
            user_create = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
            )
            try:
                await crud.create_user(session=session, user_create=user_create)
            except IntegrityError:
                await session.rollback()
                logger.info("Superuser already created by another worker, skipping.")