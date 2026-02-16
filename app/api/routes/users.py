from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.dependencies import SessionDep
from app.models import UserPublic, UserRegister, UserCreate

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.post("/register", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:

    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user
