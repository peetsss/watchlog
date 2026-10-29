from datetime import date, datetime

from lobby.dto import (
    BallotEntry,
    Capabilities,
    FinalistRef,
    JoinPreview,
    LobbyState,
    LobbySummary,
    MovieRef,
    PlayerRef,
    VoteTally,
)


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def movie_to_dict(movie: MovieRef) -> dict[str, object]:
    return {
        "id": movie.id,
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "release_date": _iso(movie.release_date),
        "poster_path": movie.poster_path,
        "backdrop_path": movie.backdrop_path,
        "description": movie.description,
        "runtime": movie.runtime,
        "genres": movie.genres,
        "director": movie.director,
    }


def _movie_or_none(movie: MovieRef | None) -> dict[str, object] | None:
    return movie_to_dict(movie) if movie is not None else None


def player_to_dict(player: PlayerRef) -> dict[str, object]:
    return {
        "user_id": player.user_id,
        "username": player.username,
        "is_host": player.is_host,
        "is_ready": player.is_ready,
    }


def _ballot_to_dict(entry: BallotEntry) -> dict[str, object]:
    return {
        "user_id": entry.user_id,
        "username": entry.username,
        "choice": entry.choice,
    }


def _tally_to_dict(tally: VoteTally | None) -> dict[str, object] | None:
    if tally is None:
        return None
    return {
        "interested": tally.interested,
        "watched": tally.watched,
        "not_interested": tally.not_interested,
        "total": tally.interested + tally.watched + tally.not_interested,
    }


def _finalist_to_dict(finalist: FinalistRef) -> dict[str, object]:
    return {
        "movie": movie_to_dict(finalist.movie),
        "pick_count": finalist.pick_count,
        "viewer_picked": finalist.viewer_picked,
    }


def _capabilities_to_dict(capabilities: Capabilities) -> dict[str, bool]:
    return {
        "can_start": capabilities.can_start,
        "can_unready": capabilities.can_unready,
        "can_advance": capabilities.can_advance,
        "can_next_round": capabilities.can_next_round,
        "can_finalize": capabilities.can_finalize,
        "can_end": capabilities.can_end,
        "can_leave": capabilities.can_leave,
        "can_restart": capabilities.can_restart,
    }


def state_to_dict(state: LobbyState) -> dict[str, object]:
    return {
        "uuid": str(state.uuid),
        "type": state.type,
        "status": state.status,
        "version": state.version,
        "host_id": state.host_id,
        "group_uuid": str(state.group_uuid) if state.group_uuid is not None else None,
        "group_name": state.group_name,
        "created_at": _iso(state.created_at),
        "started_at": _iso(state.started_at),
        "finished_at": _iso(state.finished_at),
        "viewer_id": state.viewer_id,
        "viewer_is_host": state.viewer_is_host,
        "viewer_ready": state.viewer_ready,
        "players": [player_to_dict(player) for player in state.players],
        "player_count": state.player_count,
        "ready_count": state.ready_count,
        "pool_size": state.pool_size,
        "pool_index": state.pool_index,
        "round_number": state.round_number,
        "remaining_count": state.remaining_count,
        "current_movie": _movie_or_none(state.current_movie),
        "submitted_count": state.submitted_count,
        "viewer_vote": state.viewer_vote,
        "revealed": state.revealed,
        "vote_tally": _tally_to_dict(state.vote_tally),
        "ballot": [_ballot_to_dict(entry) for entry in state.ballot],
        "finalists": [_finalist_to_dict(finalist) for finalist in state.finalists],
        "picks_revealed": state.picks_revealed,
        "viewer_pick": state.viewer_pick,
        "winner": _movie_or_none(state.winner),
        "capabilities": _capabilities_to_dict(state.capabilities),
    }


def preview_to_dict(preview: JoinPreview) -> dict[str, object]:
    return {
        "uuid": str(preview.uuid),
        "type": preview.type,
        "status": preview.status,
        "group_uuid": str(preview.group_uuid) if preview.group_uuid is not None else None,
        "group_name": preview.group_name,
        "host_username": preview.host_username,
        "player_count": preview.player_count,
        "can_join": preview.can_join,
        "is_member": preview.is_member,
    }


def summary_to_dict(summary: LobbySummary) -> dict[str, object]:
    return {
        "uuid": str(summary.uuid),
        "type": summary.type,
        "status": summary.status,
        "group_uuid": str(summary.group_uuid) if summary.group_uuid is not None else None,
        "group_name": summary.group_name,
        "host_username": summary.host_username,
        "player_count": summary.player_count,
        "current_movie_title": summary.current_movie_title,
        "created_at": _iso(summary.created_at),
    }


def error_to_dict(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}
