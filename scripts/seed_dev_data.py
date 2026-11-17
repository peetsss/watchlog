import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pwdlib import PasswordHash  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.models.group import Group, GroupMembership, GroupMovie, Review  # noqa: E402
from app.models.movie import Movie  # noqa: E402
from app.models.user import User  # noqa: E402

PASSWORD = "correct horse"
GROUP_NAME = "Friday Film Club"
USER_EMAILS = {
    "alice": "alice@example.com",
    "bob": "bob@example.com",
    "carol": "carol@example.com",
}
USERNAMES = tuple(USER_EMAILS)
TMDB_IDS = (27205, 155, 157336)
SCORES = {
    27205: {"alice": 8.5, "bob": 7.0, "carol": 9.0},
    155: {"alice": 8.0},
}


def _get_or_create_user(session: Session, username: str, email: str, password_hash: PasswordHash) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is not None:
        if user.email is None:
            user.email = email
            user.email_verified_at = datetime.now(UTC)
        return user
    user = User(
        username=username,
        email=email,
        email_verified_at=datetime.now(UTC),
        password_hash=password_hash.hash(PASSWORD),
    )
    session.add(user)
    session.flush()
    return user


def _get_or_create_group(session: Session) -> Group:
    group = session.scalar(select(Group).where(Group.name == GROUP_NAME))
    if group is not None:
        return group
    group = Group(name=GROUP_NAME, description="A weekly film club.")
    session.add(group)
    session.flush()
    return group


def _ensure_membership(session: Session, group: Group, user: User, role: str) -> None:
    membership = session.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        session.add(GroupMembership(group_id=group.id, user_id=user.id, role=role))


def _get_or_create_group_movie(session: Session, group: Group, movie: Movie, suggested_by: User) -> GroupMovie:
    group_movie = session.scalar(
        select(GroupMovie).where(
            GroupMovie.group_id == group.id,
            GroupMovie.movie_id == movie.id,
        )
    )
    if group_movie is not None:
        return group_movie
    group_movie = GroupMovie(
        group_id=group.id,
        movie_id=movie.id,
        suggested_by_id=suggested_by.id,
    )
    session.add(group_movie)
    session.flush()
    return group_movie


def _upsert_review(session: Session, group_movie: GroupMovie, user: User, score: float) -> None:
    review = session.scalar(
        select(Review).where(
            Review.group_movie_id == group_movie.id,
            Review.user_id == user.id,
        )
    )
    value = Decimal(str(score))
    if review is None:
        session.add(Review(group_movie_id=group_movie.id, user_id=user.id, score=value))
    else:
        review.score = value


def _refresh_statuses(session: Session, group: Group) -> None:
    member_count = session.scalar(
        select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == group.id)
    )
    if not member_count:
        return
    group_movies = list(session.scalars(select(GroupMovie).where(GroupMovie.group_id == group.id)))
    for group_movie in group_movies:
        score_count = session.scalar(
            select(func.count(Review.id))
            .join(
                GroupMembership,
                (GroupMembership.user_id == Review.user_id) & (GroupMembership.group_id == group.id),
            )
            .where(Review.group_movie_id == group_movie.id)
        )
        group_movie.status = "watched" if (score_count or 0) >= member_count else "up_next"


def main() -> None:
    settings = Settings()
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    password_hash = PasswordHash.recommended()

    with Session(engine) as session:
        users = [_get_or_create_user(session, username, USER_EMAILS[username], password_hash) for username in USERNAMES]
        group = _get_or_create_group(session)
        _ensure_membership(session, group, users[0], "admin")
        for user in users[1:]:
            _ensure_membership(session, group, user, "member")

        movies = list(session.scalars(select(Movie).where(Movie.tmdb_id.in_(TMDB_IDS))))
        if not movies:
            raise SystemExit("No catalog movies found; run the catalog copy first")

        for movie in movies:
            group_movie = _get_or_create_group_movie(session, group, movie, users[0])
            for username, score in SCORES.get(movie.tmdb_id or 0, {}).items():
                user = next(candidate for candidate in users if candidate.username == username)
                _upsert_review(session, group_movie, user, score)

        session.flush()
        _refresh_statuses(session, group)
        session.commit()

        print(f"seed: users={', '.join(USERNAMES)} password={PASSWORD!r}")
        print(f"seed: group={group.name} id={group.id}")
        for movie in movies:
            print(f"seed: film tmdb_id={movie.tmdb_id} title={movie.title}")


if __name__ == "__main__":
    main()
