from app.core.errors import ErrorBody, ErrorEnvelope
from app.schemas.auth import (
    CSRFResponse,
    LoginRequest,
    MeEnvelope,
    RegisterRequest,
    Viewer,
    ViewerEnvelope,
    ViewerStats,
)
from app.schemas.groups import (
    AddFilmRequest,
    CreateGroupRequest,
    FilmStatusRequest,
    GroupDetail,
    GroupFilm,
    GroupFilmList,
    GroupFilmScores,
    GroupList,
    GroupMember,
    GroupPreview,
    GroupStats,
    MemberScore,
    MemberScoreStats,
    MovieSummary,
    ScoreRequest,
)
from app.schemas.lobby import (
    ActiveEnvelope,
    BallotEntry,
    Capabilities,
    CreateLobbyRequest,
    FinalistRef,
    JoinPreview,
    JoinPreviewEnvelope,
    LobbyState,
    LobbyStateEnvelope,
    LobbySummary,
    MovieRef,
    PlayerRef,
    VoteTally,
)
from app.schemas.movies import MovieDetail, MovieSearchEnvelope, MovieSearchResult

EXPECTED_PATHS = {
    "/",
    "/api/auth/csrf",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/register",
    "/api/groups",
    "/api/groups/{group_id}",
    "/api/groups/{group_id}/films",
    "/api/groups/{group_id}/films/{film_id}",
    "/api/groups/{group_id}/films/{film_id}/score",
    "/api/groups/{group_id}/films/{film_id}/scores",
    "/api/groups/{group_id}/invite",
    "/api/groups/{group_id}/lobbies",
    "/api/groups/{group_id}/members",
    "/api/groups/{group_id}/members/me",
    "/api/groups/{group_id}/preview",
    "/api/groups/{group_id}/stats",
    "/api/groups/{group_id}/watchlist",
    "/api/lobby/",
    "/api/lobby/active/",
    "/api/lobby/{lobby_uuid}/",
    "/api/lobby/{lobby_uuid}/join/",
    "/api/lobby/{lobby_uuid}/preview/",
    "/api/lobby/{lobby_uuid}/{action}/",
    "/api/me",
    "/api/movies/search",
    "/api/movies/{movie_id}",
}


def _fields(model: type) -> set[str]:
    return set(model.model_fields)


def test_documented_paths_are_frozen() -> None:
    from app.main import app

    assert set(app.openapi()["paths"]) == EXPECTED_PATHS


def test_auth_contract_fields() -> None:
    assert _fields(Viewer) == {"mode", "id", "username", "initials", "color"}
    assert _fields(ViewerStats) == {"titles_watched", "average_score"}
    assert _fields(ViewerEnvelope) == {"viewer"}
    assert _fields(MeEnvelope) == {"viewer", "stats"}
    assert _fields(CSRFResponse) == {"csrf_token"}
    assert CSRFResponse.model_fields["csrf_token"].serialization_alias == "csrfToken"
    assert _fields(RegisterRequest) == {"username", "password"}
    assert _fields(LoginRequest) == {"username", "password"}


def test_group_contract_fields() -> None:
    assert _fields(GroupMember) == {"id", "username", "initials", "color", "role"}
    assert _fields(GroupDetail) == {
        "id",
        "name",
        "description",
        "member_count",
        "film_count",
        "members",
        "created_at",
    }
    assert _fields(GroupList) == {"groups"}
    assert _fields(GroupPreview) == {
        "id",
        "name",
        "description",
        "member_count",
        "film_count",
        "is_member",
    }
    assert _fields(MovieSummary) == {
        "id",
        "tmdb_id",
        "title",
        "release_date",
        "runtime",
        "genres",
        "director",
        "description",
        "poster_path",
        "backdrop_path",
    }
    assert _fields(GroupFilm) == {
        "id",
        "movie",
        "status",
        "added_at",
        "added_by",
        "club_score",
        "score_count",
        "your_score",
    }
    assert _fields(GroupFilmList) == {"films"}
    assert _fields(GroupFilmScores) == {"film_id", "scores"}
    assert _fields(MemberScore) == {"user_id", "username", "initials", "color", "score"}
    assert _fields(MemberScoreStats) == {"user_id", "username", "score_count", "average_score"}
    assert _fields(GroupStats) == {
        "film_count",
        "watched_count",
        "up_next_count",
        "member_count",
        "average_score",
        "member_scores",
    }
    assert _fields(CreateGroupRequest) == {"name", "description"}
    assert _fields(AddFilmRequest) == {"tmdb_id", "media_type"}
    assert _fields(ScoreRequest) == {"score"}
    assert _fields(FilmStatusRequest) == {"status"}


def test_lobby_contract_fields() -> None:
    assert _fields(PlayerRef) == {"id", "name", "initials", "color", "is_host", "is_guest", "is_ready"}
    assert _fields(MovieRef) == {
        "id",
        "tmdb_id",
        "title",
        "release_date",
        "poster_path",
        "backdrop_path",
        "description",
        "runtime",
        "genres",
        "director",
    }
    assert _fields(BallotEntry) == {"participant_id", "name", "choice"}
    assert _fields(VoteTally) == {"interested", "watched", "not_interested", "total"}
    assert _fields(FinalistRef) == {"movie", "pick_count", "viewer_picked"}
    assert _fields(Capabilities) == {
        "can_start",
        "can_unready",
        "can_advance",
        "can_next_round",
        "can_finalize",
        "can_end",
        "can_leave",
        "can_restart",
    }
    assert _fields(LobbyState) == {
        "uuid",
        "type",
        "status",
        "version",
        "host_id",
        "group_uuid",
        "group_name",
        "created_at",
        "started_at",
        "finished_at",
        "viewer_id",
        "viewer_is_host",
        "viewer_ready",
        "players",
        "player_count",
        "ready_count",
        "pool_size",
        "pool_index",
        "round_number",
        "remaining_count",
        "current_movie",
        "submitted_count",
        "viewer_vote",
        "revealed",
        "vote_tally",
        "ballot",
        "finalists",
        "picks_revealed",
        "viewer_pick",
        "winner",
        "capabilities",
    }
    assert _fields(LobbyStateEnvelope) == {"lobby"}
    assert _fields(JoinPreview) == {
        "uuid",
        "type",
        "status",
        "group_uuid",
        "group_name",
        "host_username",
        "player_count",
        "can_join",
        "is_member",
    }
    assert _fields(JoinPreviewEnvelope) == {"preview"}
    assert _fields(LobbySummary) == {
        "uuid",
        "type",
        "status",
        "group_uuid",
        "group_name",
        "host_username",
        "player_count",
        "current_movie_title",
        "created_at",
    }
    assert _fields(ActiveEnvelope) == {"active"}
    assert _fields(CreateLobbyRequest) == {"group_uuid"}


def test_movie_contract_fields() -> None:
    assert _fields(MovieSearchResult) == {"tmdb_id", "title", "year", "poster_url", "media_type", "movie_id"}
    assert _fields(MovieSearchEnvelope) == {"movies"}
    assert _fields(MovieDetail) == {
        "id",
        "tmdb_id",
        "imdb_id",
        "title",
        "original_title",
        "media_type",
        "description",
        "tagline",
        "status",
        "runtime",
        "release_date",
        "adult",
        "genres",
        "keywords",
        "director",
        "writers",
        "actors",
        "country",
        "original_language",
        "spoken_languages",
        "production_companies",
        "poster_path",
        "backdrop_path",
        "awards",
        "revenue",
        "budget",
        "tmdb_score",
        "vote_count",
        "popularity",
        "imdb_score",
        "rottentomato_score",
        "metacritic_score",
        "filmweb_score",
        "imdb_url",
        "rottentomato_url",
        "metacritic_url",
        "filmweb_url",
        "homepage",
        "created_at",
        "updated_at",
    }


def test_error_contract_fields() -> None:
    assert _fields(ErrorEnvelope) == {"error"}
    assert _fields(ErrorBody) == {"code", "message"}
