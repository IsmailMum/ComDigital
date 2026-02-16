from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

password_hash = PasswordHash(
    (
        BcryptHasher(),
    )
)

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
