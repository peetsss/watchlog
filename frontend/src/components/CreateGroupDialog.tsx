import { useState, type FormEvent } from "react";
import { Loader2, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useCreateGroup } from "../lib/api-groups";
import { ApiError } from "../lib/api";
import { useToast } from "../state/Toast";
import { Button } from "./Button";
import { Modal } from "./Modal";

export function CreateGroupDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createGroup = useCreateGroup();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setDescription("");
    setError(null);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && !createGroup.isPending) reset();
    onOpenChange(next);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed.length < 2) {
      setError("Give the group a name with at least two characters.");
      return;
    }

    setError(null);
    try {
      const group = await createGroup.mutateAsync({
        name: trimmed,
        description: description.trim(),
      });
      showToast(`${group.name} is ready. Invite your people.`);
      reset();
      onOpenChange(false);
      navigate(`/groups/${group.id}`);
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Couldn't create the group. Try again.",
      );
    }
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title="Create a group"
      description="A group is the people you watch with and the movies you keep between you."
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => handleOpenChange(false)}
            disabled={createGroup.isPending}
          >
            Cancel
          </Button>
          <Button type="submit" form="create-group-form" disabled={createGroup.isPending}>
            {createGroup.isPending ? (
              <>
                <Loader2 className="spin" size={16} /> Creating…
              </>
            ) : (
              <>
                <Plus size={16} /> Create group
              </>
            )}
          </Button>
        </>
      }
    >
      <form id="create-group-form" onSubmit={handleSubmit} noValidate>
        <label className="field-label" htmlFor="group-name">
          Group name
        </label>
        <input
          id="group-name"
          className="text-input"
          type="text"
          value={name}
          autoComplete="off"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "group-name-error" : undefined}
          onChange={(event) => {
            setName(event.target.value);
            if (error) setError(null);
          }}
          placeholder="The Sunday Matinee"
        />
        {error ? (
          <p className="field-error" id="group-name-error" role="alert">
            {error}
          </p>
        ) : null}

        <label className="field-label field-label-spaced" htmlFor="group-description">
          What's the group about? <span className="field-optional">Optional</span>
        </label>
        <textarea
          id="group-description"
          className="text-input text-area"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Long movies, longer debates. No phones at the table."
        />
      </form>

      <p className="field-help">You'll be the first member. You can invite people after the group exists.</p>
    </Modal>
  );
}
