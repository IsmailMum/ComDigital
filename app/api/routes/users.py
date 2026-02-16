from datetime import timedelta
from typing import Any, Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from app import crud
from app.api.dependencies import SessionDep, CurrentUser
from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    InactiveUserError,
)
from app.models import UserPublic, UserRegister, UserCreate, Token, UserUpdateMe

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/register", response_model=UserPublic)
async def register_user(session: SessionDep, user_in: UserRegister) -> Any:

    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise UserAlreadyExistsError()

    try:
        user_create = UserCreate.model_validate(user_in)
        user = await crud.create_user(session=session, user_create=user_create)
    except IntegrityError:
        await session.rollback()
        raise UserAlreadyExistsError()
    return user


@router.post("/login")
async def login(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise InvalidCredentialsError()
    elif not user.is_active:
        raise InactiveUserError()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.get("/profile", response_model=UserPublic)
async def get_current_user(current_user: CurrentUser) -> Any:
    return current_user


@router.patch("/profile", response_model=UserPublic)
async def update_current_user(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    return await crud.update_user(session=session, db_user=current_user, user_in=user_in)