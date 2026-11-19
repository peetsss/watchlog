import logging
import re

_TOKEN_QUERY = re.compile(r"(?i)\b(token|api_key|access_token|csrf|password)=([^&\s\"']+)")
_INVITE_PATH = re.compile(r"(?i)(/(?:api/group-invites|join/group)/)([^/?#\s\"']+)")
_BEARER = re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9._~+/=-]+)")


def redact_text(value: str) -> str:
    value = _TOKEN_QUERY.sub(r"\1=[REDACTED]", value)
    value = _INVITE_PATH.sub(r"\1[REDACTED]", value)
    value = _BEARER.sub(r"\1[REDACTED]", value)
    return value


def redact_path(path: str) -> str:
    value = redact_text(path)
    return "".join(character if character.isprintable() else "?" for character in value)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = None
        if isinstance(message, str):
            redacted = redact_text(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
                return True
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_text(arg) if isinstance(arg, str) else arg for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_text(value) if isinstance(value, str) else value for key, value in record.args.items()
            }
        return True
