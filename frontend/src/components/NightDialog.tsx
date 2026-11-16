import { Star } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, buttonClass } from "../components/Button";
import { Modal } from "../components/Modal";
import type { RecentNight } from "../data";
import type { ScoredMember } from "../pages/group/score";

export function NightDialog({
  night,
  score,
  open,
  onOpenChange,
}: {
  night: RecentNight | null;
  score: { average: number; count: number; scored: ScoredMember[] } | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!night) return null;

  const average = score?.average ?? night.rating;
  const count = score?.count ?? 0;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={night.movie.title}
      description={`${night.date} · ${night.group}`}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Link to={`/groups/${night.groupId}`} className={buttonClass("secondary", "md")}>
            Open the group
          </Link>
        </>
      }
    >
      <div className="night-dialog-card">
        <div className="night-dialog-poster">
          <img src={night.movie.poster} alt={`${night.movie.title} poster`} />
        </div>
        <div className="night-dialog-copy">
          <span
            className="night-dialog-rating"
            aria-label={
              count
                ? `Club score ${average.toFixed(1)} from ${count} ${count === 1 ? "score" : "scores"}`
                : `Night score ${average.toFixed(1)}`
            }
          >
            <Star size={14} fill="currentColor" aria-hidden="true" /> {average.toFixed(1)}
            <span>
              {count ? `${count} ${count === 1 ? "score" : "scores"}` : "night score"}
            </span>
          </span>
          {score?.scored.length ? (
            <span className="night-dialog-track" aria-hidden="true">
              {score.scored.map(({ person, score: value }) => (
                <span
                  key={person.id}
                  className="night-dialog-dot"
                  style={{ left: `${value * 10}%`, background: person.color }}
                />
              ))}
            </span>
          ) : null}
          <p>{night.note}</p>
          <span className="night-dialog-credit">
            {night.movie.year} · {night.movie.runtime} min · Dir. {night.movie.director}
          </span>
        </div>
      </div>
    </Modal>
  );
}
