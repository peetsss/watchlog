from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

_password_hash = PasswordHash.recommended()


def _hash(password: str) -> str:
    return _password_hash.hash(password)


def _verify(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await run_in_threadpool(_verify, password, password_hash)
