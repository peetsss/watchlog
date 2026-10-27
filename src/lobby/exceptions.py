class LobbyError(Exception):
    pass


class LobbyNotFoundError(LobbyError):
    pass


class NotAMemberError(LobbyError):
    pass


class NotHostError(LobbyError):
    pass


class NotJoinableError(LobbyError):
    pass


class InvalidStateError(LobbyError):
    pass


class InvalidChoiceError(LobbyError):
    pass


class AlreadyActiveLobbyError(LobbyError):
    pass


class InvalidPoolError(LobbyError):
    pass
