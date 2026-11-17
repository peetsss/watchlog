import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redis import Redis  # noqa: E402
from sqlalchemy import create_engine, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.sessions import USER_SESSIONS_PREFIX  # noqa: E402
from app.models.email import EmailOutbox  # noqa: E402
from app.models.group import Group  # noqa: E402
from app.models.invite import GroupInvite  # noqa: E402
from app.models.user import User  # noqa: E402


def _user(session: Session, username: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise SystemExit(f"No user named {username!r}")
    return user


def _group(session: Session, group_id: str) -> Group:
    try:
        uuid = UUID(group_id)
    except ValueError as exc:
        raise SystemExit(f"Invalid group UUID: {group_id!r}") from exc
    group = session.get(Group, uuid)
    if group is None:
        raise SystemExit(f"No group with id {group_id!r}")
    return group


def cmd_user(session: Session, args: argparse.Namespace) -> None:
    user = _user(session, args.username)
    if args.action == "disable":
        user.is_active = False
        session.commit()
        print(f"disabled {user.username}")
    elif args.action == "enable":
        user.is_active = True
        session.commit()
        print(f"enabled {user.username}")
    elif args.action == "revoke-sessions":
        settings = Settings()
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        key = f"{USER_SESSIONS_PREFIX}{user.id}"
        session_hashes = redis.smembers(key)
        if session_hashes:
            redis.delete(*[f"watchlog:sess:{session_hash}" for session_hash in session_hashes])
        redis.delete(key)
        redis.close()
        print(f"revoked {len(session_hashes)} session(s) for {user.username}")


def cmd_group(session: Session, args: argparse.Namespace) -> None:
    group = _group(session, args.group_id)
    if args.action == "delete":
        session.delete(group)
        session.commit()
        print(f"deleted group {group.id}")
    elif args.action == "revoke-invites":
        result = session.execute(
            update(GroupInvite)
            .where(GroupInvite.group_id == group.id, GroupInvite.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        session.commit()
        print(f"revoked {int(result.rowcount or 0)} invite(s) for {group.name}")


def cmd_email(session: Session, args: argparse.Namespace) -> None:
    statement = update(EmailOutbox)
    if args.outbox_id is not None:
        statement = statement.where(EmailOutbox.id == args.outbox_id)
    else:
        statement = statement.where(EmailOutbox.recipient == args.recipient.lower())
    result = session.execute(
        statement.values(status="pending", attempts=0, next_attempt_at=datetime.now(UTC), last_error=None)
    )
    session.commit()
    print(f"requeued {int(result.rowcount or 0)} email(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="watchlog operational CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    user_parser = subparsers.add_parser("user")
    user_parser.add_argument("action", choices=("disable", "enable", "revoke-sessions"))
    user_parser.add_argument("username")
    user_parser.set_defaults(handler=cmd_user)

    group_parser = subparsers.add_parser("group")
    group_parser.add_argument("action", choices=("delete", "revoke-invites"))
    group_parser.add_argument("group_id")
    group_parser.set_defaults(handler=cmd_group)

    email_parser = subparsers.add_parser("email")
    email_parser.add_argument("action", choices=("requeue",))
    email_parser.add_argument("--id", dest="outbox_id", type=int)
    email_parser.add_argument("--recipient", default="")
    email_parser.set_defaults(handler=cmd_email)

    args = parser.parse_args()
    if args.command == "email" and args.outbox_id is None and not args.recipient:
        raise SystemExit("email requeue needs --id or --recipient")

    settings = Settings()
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    with Session(engine) as session:
        args.handler(session, args)


if __name__ == "__main__":
    main()
