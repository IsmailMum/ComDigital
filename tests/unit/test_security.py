from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    get_password_hash,
    create_access_token,
    verify_password,
)


class TestGetPasswordHash:
    def test_returns_bcrypt_hash(self):
        hashed = get_password_hash("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert hashed.startswith("$2")

    def test_different_passwords_produce_different_hashes(self):
        h1 = get_password_hash("password1")
        h2 = get_password_hash("password2")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password(self):
        hashed = get_password_hash("correctpassword")
        verified, _ = verify_password("correctpassword", hashed)
        assert verified is True

    def test_wrong_password(self):
        hashed = get_password_hash("correctpassword")
        verified, _ = verify_password("wrongpassword", hashed)
        assert verified is False


class TestCreateAccessToken:
    def test_returns_valid_jwt(self):
        token = create_access_token("user-123", expires_delta=timedelta(minutes=30))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-123"
        assert "exp" in payload

    def test_expiry_is_set(self):
        token = create_access_token("user-456", expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
