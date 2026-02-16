from typing import Annotated

from fastapi import Depends
from sqlmodel import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import engine
from app.core.db import async_session


async def get_db():
    async with async_session() as session:
        yield session

SessionDep = Annotated[Session, Depends(get_db)]
SessionDep = Annotated[AsyncSession, Depends(get_db)]
