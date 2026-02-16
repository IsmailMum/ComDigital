from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

password_hash = PasswordHash(
    (
        Argon2Hasher(),
    )
)

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
