from sqlmodel import Session, select, create_engine

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:

    superuser = session.exec(
        select(User).where(User.is_superuser == True)
    ).first()

    if not superuser:
        superuser = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )

        crud.create_user(session=session, user_create=superuser)