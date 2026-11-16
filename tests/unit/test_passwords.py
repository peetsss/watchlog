from app.services.passwords import hash_password, verify_password


async def test_hash_and_verify_password() -> None:
    password = "correct horse battery staple"

    password_hash = await hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert await verify_password(password, password_hash)
    assert not await verify_password("wrong password", password_hash)
