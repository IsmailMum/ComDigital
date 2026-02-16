import logging
from typing import Annotated

import jwt
import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.cache import get_redis
from app.core.config import settings
from app.core.db import async_session
from app.core.exceptions import (
    CredentialsValidationError,
    UserNotFoundError,
    InactiveUserError,
)
from app.models import User, TokenPayload

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login"
)

async def get_db():
    async with async_session() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        logger.warning("Token validation failed: invalid or expired token")
        raise CredentialsValidationError()
    user = await session.get(User, token_data.sub)
    if not user:
        logger.warning("Token references non-existent user: sub=%s", token_data.sub)
        raise UserNotFoundError()
    if not user.is_active:
        logger.warning("Token belongs to inactive user: id=%s", user.id)
        raise InactiveUserError()
    logger.debug("Authenticated user from token: id=%s, email=%s", user.id, user.email)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]
