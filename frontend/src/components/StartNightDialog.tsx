import { useEffect, useState } from "react";
import { ArrowRight, Check, Info, Link2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useGroups } from "../state/Groups";
import { useLobby } from "../state/Lobby";
import { cx } from "../lib/cx";
import { Button } from "./Button";
import { Modal } from "./Modal";
import { PosterStack } from "./PosterStack";

export function StartNightDialog({
  open,
  onOpenChange,
  initialGroupId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialGroupId?: string;
}) {
  const { groups } = useGroups();
  const { startLobby } = useLobby();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"group" | "open">("group");
  const [groupId, setGroupId] = useState(initialGroupId ?? groups[0]?.id ?? "");

  useEffect(() => {
    if (mode === "group" && !groups.some((group) => group.id === groupId)) {
      setGroupId(groups[0]?.id ?? "");
    }
  }, [groups, groupId, mode]);

  const selectedGroup = groups.find((group) => group.id === groupId) ?? null;
  const canStart = mode === "open" || Boolean(selectedGroup);

  const handleStart = () => {
    if (!canStart) return;
    startLobby(mode === "group" ? selectedGroup : null, mode === "open");
    onOpenChange(false);
    navigate("/lobby/friday");
  };

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Start a movie night"
      description="Pick a crew, or open the door. You can share the link once the room is up."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleStart} disabled={!canStart}>
            Start the room <ArrowRight size={16} />
          </Button>
        </>
      }
    >
      <div className="choice-label">With a group</div>
      <div className="choice-list" role="group" aria-label="Choose a group">
        {groups.map((group) => {
          const selected = mode === "group" && group.id === groupId;
          return (
            <button
              key={group.id}
              type="button"
              className={cx("choice", selected && "is-selected")}
              aria-pressed={selected}
              onClick={() => {
                setMode("group");
                setGroupId(group.id);
              }}
            >
              <PosterStack movies={group.watchlist} className="choice-posters" />
              <span className="choice-copy">
                <strong>{group.name}</strong>
                <span>
                  {group.members.length}{" "}
                  {group.members.length === 1 ? "member" : "members"} · {group.films.length}{" "}
                  {group.films.length === 1 ? "film" : "films"}
                </span>
              </span>
              <span className="choice-check" aria-hidden="true">
                {selected ? <Check size={15} strokeWidth={2.6} /> : null}
              </span>
            </button>
          );
        })}
        {groups.length === 0 ? (
          <p className="field-help">No groups yet — open the door and start with a link.</p>
        ) : null}
      </div>

      <div className="choice-divider">
        <span>or</span>
      </div>

      <button
        type="button"
        className={cx("choice choice-open", mode === "open" && "is-selected")}
        aria-pressed={mode === "open"}
        onClick={() => setMode("open")}
      >
        <span className="choice-icon" aria-hidden="true">
          <Link2 size={19} />
        </span>
        <span className="choice-copy">
          <strong>Open lobby</strong>
          <span>Anyone with the link can join. Not listed publicly.</span>
        </span>
        <span className="choice-check" aria-hidden="true">
          {mode === "open" ? <Check size={15} strokeWidth={2.6} /> : null}
        </span>
      </button>

      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>
          {mode === "open"
            ? "The link is the only key. The room never appears in a public list."
            : selectedGroup
              ? `Only ${selectedGroup.name} members can join this room.`
              : "Choose a group or an open lobby to continue."}
        </span>
      </div>
    </Modal>
  );
}
