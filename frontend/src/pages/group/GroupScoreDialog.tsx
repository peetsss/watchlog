import { useEffect, useState } from "react";
import { Info, Star } from "lucide-react";
import { Button } from "../../components/Button";
import { Modal } from "../../components/Modal";
import { YOU, type Group, type GroupFilm } from "../../data";
import { movieForFilm } from "./score";

export function GroupScoreDialog({
  group,
  film,
  open,
  onOpenChange,
  onSave,
}: {
  group: Group;
  film: GroupFilm | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (score: number) => void;
}) {
  const movie = movieForFilm(film);
  const [value, setValue] = useState(film?.scores[YOU] ?? 8);

  useEffect(() => {
    if (open) setValue(film?.scores[YOU] ?? 8);
  }, [film, open]);

  if (!film || !movie) return null;

  const watched = film.status === "watched";

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={watched ? "Your score" : "Mark it watched"}
      description={
        watched
          ? `One score per member. The group average updates when you save.`
          : `${movie.title} moves into the watched list. Add the score the club gave it.`
      }
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => onSave(Number(value.toFixed(1)))}>
            {watched ? "Save score" : "Mark watched"}
          </Button>
        </>
      }
    >
      <div className="group-score-dialog">
        <div className="group-score-dialog-poster">
          <img src={movie.poster} alt={`${movie.title} poster`} />
        </div>
        <div className="group-score-dialog-body">
          <span className="group-score-dialog-label">
            <Star size={12} fill="currentColor" aria-hidden="true" /> Your score
          </span>
          <div className="group-score-dialog-value">{value.toFixed(1)}</div>
          <input
            className="group-score-dialog-range"
            type="range"
            min={1}
            max={10}
            step={0.1}
            value={value}
            aria-label={`Score for ${movie.title}`}
            onChange={(event) => setValue(Number(event.target.value))}
          />
          <div className="group-score-dialog-scale" aria-hidden="true">
            <span>1</span>
            <span>5</span>
            <span>10</span>
          </div>
        </div>
      </div>
      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>
          Scores are shared with {group.name}. The club average is the mean of the members who
          scored it.
        </span>
      </div>
    </Modal>
  );
}
