import { useEffect, useState } from "react";
import { Info, Loader2, Star } from "lucide-react";
import { Button } from "../../components/Button";
import { Modal } from "../../components/Modal";
import { MoviePoster } from "../../components/MoviePoster";
import type { GroupFilmView } from "../../lib/adapters";
import { ApiError } from "../../lib/api";

export function GroupScoreDialog({
  groupName,
  film,
  open,
  onOpenChange,
  onSave,
}: {
  groupName: string;
  film: GroupFilmView | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (score: number) => Promise<void>;
}) {
  const [value, setValue] = useState(film?.yourScore ?? 8);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setValue(film?.yourScore ?? 8);
    setError(null);
    setBusy(false);
  }, [film, open]);

  if (!film) return null;

  const watched = film.status === "watched";

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    try {
      await onSave(Number(value.toFixed(1)));
      onOpenChange(false);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError ? saveError.message : "Couldn't save your score. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!busy) onOpenChange(next);
      }}
      title={watched ? "Your score" : "Mark it watched"}
      description={
        watched
          ? "One score per member. The group average updates when you save."
          : `${film.movie.title} moves into the watched list. Add the score the club gave it.`
      }
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={busy}>
            {busy ? (
              <>
                <Loader2 className="spin" size={15} /> Saving…
              </>
            ) : watched ? (
              "Save score"
            ) : (
              "Mark watched"
            )}
          </Button>
        </>
      }
    >
      <div className="group-score-dialog">
        <div className="group-score-dialog-poster">
          <MoviePoster src={film.movie.poster} title={film.movie.title} />
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
            aria-label={`Score for ${film.movie.title}`}
            onChange={(event) => setValue(Number(event.target.value))}
          />
          <div className="group-score-dialog-scale" aria-hidden="true">
            <span>1</span>
            <span>5</span>
            <span>10</span>
          </div>
        </div>
      </div>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>
          Scores are shared with {groupName}. The club average is the mean of the members who
          scored it.
        </span>
      </div>
    </Modal>
  );
}
