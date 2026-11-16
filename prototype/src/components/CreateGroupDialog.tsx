import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { useGroups } from "../state/Groups";
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
  const { createGroup } = useGroups();
  const { showToast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setDescription("");
    setError(null);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed.length < 2) {
      setError("Give the group a name with at least two characters.");
      return;
    }

    createGroup(trimmed, description.trim());
    showToast(`${trimmed} is ready. Invite your people.`);
    reset();
    onOpenChange(false);
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title="Create a group"
      description="A group is the people you watch with and the films you keep between you."
      footer={
        <>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="create-group-form">
            <Plus size={16} /> Create group
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
          placeholder="Long films, longer debates. No phones at the table."
        />
      </form>

      <p className="field-help">You'll be the first member. You can invite people after the group exists.</p>
    </Modal>
  );
}
