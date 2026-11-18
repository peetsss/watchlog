import logging

from httpx import AsyncClient

from tests.api.helpers import csrf_token


async def test_request_log_redacts_invite_tokens(
    client: AsyncClient,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="app.core.middleware")

    await client.get("/join/group/invite-secret")
    await client.get("/api/group-invites/invite-secret")

    assert "invite-secret" not in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "from 127.0.0.1" in caplog.text


async def test_request_log_keeps_control_characters_out(client: AsyncClient, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.core.middleware")

    await client.get("/join/group/secret%0anext%1b")

    messages = [record.getMessage() for record in caplog.records]
    assert messages
    assert all("\n" not in message and "\x1b" not in message for message in messages)


async def test_csrf_token_is_not_logged(client: AsyncClient, caplog) -> None:
    caplog.set_level(logging.INFO)
    token = await csrf_token(client)

    assert token not in caplog.text
