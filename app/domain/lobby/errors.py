from app.domain.lobby.exceptions import (
    AlreadyActiveLobbyError,
    InvalidActionError,
    InvalidChoiceError,
    InvalidPoolError,
    InvalidStateError,
    LobbyError,
    LobbyNotFoundError,
    NotAMemberError,
    NotHostError,
    NotJoinableError,
)

_ERROR_DETAILS: tuple[tuple[type[LobbyError], int, str], ...] = (
    (LobbyNotFoundError, 404, "not_found"),
    (NotAMemberError, 403, "not_a_member"),
    (NotHostError, 403, "not_host"),
    (NotJoinableError, 409, "not_joinable"),
    (InvalidStateError, 409, "invalid_state"),
    (InvalidChoiceError, 400, "invalid_choice"),
    (InvalidPoolError, 400, "invalid_pool"),
    (InvalidActionError, 400, "invalid_action"),
    (AlreadyActiveLobbyError, 409, "already_active"),
)


def error_details(exc: LobbyError) -> tuple[int, str]:
    for error_type, status, code in _ERROR_DETAILS:
        if isinstance(exc, error_type):
            return status, code
    return 400, "lobby_error"
