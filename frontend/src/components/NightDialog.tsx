import { Loader2, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, buttonClass } from "../components/Button";
import { Modal } from "../components/Modal";
import { MoviePoster } from "../components/MoviePoster";
import { formatDate, type HomeLogEntryView } from "../lib/adapters";
import { useGroupFilmScores } from "../lib/api-groups";

export function NightDialog({
  entry,
  open,
  onOpenChange,
}: {
  entry: HomeLogEntryView | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const scoresQuery = useGroupFilmScores(entry?.groupId ?? "", entry?.filmId ?? null, open);

  if (!entry) return null;

  const movie = entry.movie;
  const scores = [...(scoresQuery.data ?? [])].sort(
    (a, b) => b.score - a.score || a.person.name.localeCompare(b.person.name),
  );
  const average = entry.clubScore ?? 0;
  const count = entry.scoreCount;
  const credit = [
    movie.year,
    movie.runtime ? `${movie.runtime} min` : null,
    movie.director ? `Dir. ${movie.director}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={movie.title}
      description={`${formatDate(entry.watchedAt)} · ${entry.groupName}`}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Link to={`/groups/${entry.groupId}`} className={buttonClass("secondary", "md")}>
            Open the group
          </Link>
        </>
      }
    >
      <div className="night-dialog-card">
        <div className="night-dialog-poster">
          <MoviePoster src={movie.poster} title={movie.title} />
        </div>
        <div className="night-dialog-copy">
          <span
            className="night-dialog-rating"
            aria-label={
              count
                ? `Club score ${average.toFixed(1)} from ${count} ${count === 1 ? "score" : "scores"}`
                : "Not scored yet"
            }
          >
            <Star size={14} fill="currentColor" aria-hidden="true" />{" "}
            {count ? average.toFixed(1) : "—"}
            <span>
              {count ? `${count} ${count === 1 ? "score" : "scores"}` : "not scored yet"}
            </span>
          </span>
          {scores.length ? (
            <span className="night-dialog-track" aria-hidden="true">
              {scores.map(({ person, score }) => (
                <span
                  key={person.id}
                  className="night-dialog-dot"
                  style={{ left: `${score * 10}%`, background: person.color }}
                />
              ))}
            </span>
          ) : null}
          {scoresQuery.isPending ? (
            <p className="night-dialog-note">
              <Loader2 className="spin" size={13} aria-hidden="true" /> Loading scores…
            </p>
          ) : (
            <p className="night-dialog-note">
              {movie.description || `${entry.groupName} watched this together.`}
            </p>
          )}
          {credit ? <span className="night-dialog-credit">{credit}</span> : null}
        </div>
      </div>
    </Modal>
  );
}
