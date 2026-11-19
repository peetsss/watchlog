import { useEffect, useState } from "react";
import { ArrowRight, Check, Info, Link2, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useGroupList } from "../lib/api-groups";
import { createLobby, joinLobby } from "../lib/api-lobby";
import { ApiError } from "../lib/api";
import { homeKeys, groupKeys, lobbyKeys } from "../lib/query-keys";
import { cx } from "../lib/cx";
import { Button } from "./Button";
import { Modal } from "./Modal";

export function StartNightDialog({
  open,
  onOpenChange,
  initialGroupId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialGroupId?: string;
}) {
  const groups = useGroupList().data ?? [];
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"group" | "open">("group");
  const [groupId, setGroupId] = useState(initialGroupId ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setBusy(false);
    setMode(initialGroupId ? "group" : groups.length ? "group" : "open");
    setGroupId(
      initialGroupId && groups.some((group) => group.id === initialGroupId)
        ? initialGroupId
        : (groups[0]?.id ?? ""),
    );
  }, [groups, initialGroupId, open]);

  const selectedGroup = groups.find((group) => group.id === groupId) ?? null;
  const activeLobby = mode === "group" ? selectedGroup?.activeLobby ?? null : null;
  const canJoinActive = Boolean(activeLobby && (activeLobby.isParticipant || activeLobby.canJoin));
  const canStart = !busy && (mode === "open" || Boolean(selectedGroup) && (!activeLobby || canJoinActive));
  const primaryLabel = activeLobby
    ? activeLobby.isParticipant
      ? "Reopen the room"
      : activeLobby.canJoin
        ? "Join the room"
        : "Night in progress"
    : "Start the room";

  const openLobby = (uuid: string) => {
    onOpenChange(false);
    navigate(`/lobby/${uuid}`);
  };

  const handleStart = async () => {
    if (!canStart) return;
    setBusy(true);
    setError(null);
    try {
      if (activeLobby) {
        if (activeLobby.isParticipant) {
          openLobby(activeLobby.uuid);
          return;
        }
        if (activeLobby.canJoin) {
          await joinLobby(activeLobby.uuid);
          void queryClient.invalidateQueries({ queryKey: homeKeys.all });
          void queryClient.invalidateQueries({ queryKey: groupKeys.all });
          void queryClient.invalidateQueries({ queryKey: lobbyKeys.active() });
          openLobby(activeLobby.uuid);
          return;
        }
      }
      const lobby = await createLobby(mode === "group" ? selectedGroup?.id : undefined);
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
      void queryClient.invalidateQueries({ queryKey: groupKeys.all });
      void queryClient.invalidateQueries({ queryKey: lobbyKeys.active() });
      openLobby(lobby.uuid);
    } catch (startError) {
      if (startError instanceof ApiError && startError.code === "already_active") {
        setError("That group already has an active room. Rejoin it from the group page.");
      } else if (startError instanceof ApiError && startError.code === "rate_limited") {
        const minutes = startError.retryAfter ? Math.max(1, Math.ceil(startError.retryAfter / 60)) : null;
        setError(
          minutes
            ? `Too many room attempts. Try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`
            : "Too many room attempts. Try again shortly.",
        );
      } else {
        setError(
          startError instanceof ApiError
            ? startError.message
            : "Couldn't start the room. Try again.",
        );
      }
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
      title="Start a movie night"
      description="Pick a crew, or open the door. You can share the link once the room is up."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleStart} disabled={!canStart}>
            {busy ? (
              <>
                <Loader2 className="spin" size={16} /> Starting…
              </>
            ) : (
              <>
                {primaryLabel} <ArrowRight size={16} />
              </>
            )}
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
              <span className="choice-icon" aria-hidden="true">
                {group.name.slice(0, 2).toUpperCase()}
              </span>
              <span className="choice-copy">
                <strong>{group.name}</strong>
                <span>
                  {group.memberCount} {group.memberCount === 1 ? "member" : "members"} ·{" "}
                  {group.filmCount} {group.filmCount === 1 ? "movie" : "movies"}
                </span>
              </span>
              <span className="choice-check" aria-hidden="true">
                {selected ? <Check size={15} strokeWidth={2.6} /> : null}
              </span>
            </button>
          );
        })}
        {!groups.length ? (
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

      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>
          {mode === "open"
            ? "The link is the only key. The room never appears in a public list."
            : selectedGroup
              ? activeLobby
                ? `${activeLobby.playerCount} ${
                    activeLobby.playerCount === 1 ? "person is" : "people are"
                  } already in the room.`
                : `Only ${selectedGroup.name} members can join this room.`
              : "Choose a group or an open lobby to continue."}
        </span>
      </div>
    </Modal>
  );
}
