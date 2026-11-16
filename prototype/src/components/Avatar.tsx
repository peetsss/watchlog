import type { Person } from "../data";
import { cx } from "../lib/cx";

export function Avatar({
  person,
  size = 36,
  className,
}: {
  person: Person;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={cx("avatar", className)}
      style={{
        width: size,
        height: size,
        background: person.color,
        fontSize: Math.max(9, Math.round(size * 0.31)),
      }}
      aria-hidden="true"
    >
      {person.short}
    </span>
  );
}

export function AvatarStack({
  people,
  max = 4,
  size = 28,
  className,
}: {
  people: Person[];
  max?: number;
  size?: number;
  className?: string;
}) {
  const shown = people.slice(0, max);
  const extra = people.length - shown.length;

  return (
    <span
      className={cx("avatar-stack", className)}
      role="img"
      aria-label={people.map((person) => person.name).join(", ")}
    >
      {shown.map((person) => (
        <Avatar key={person.id} person={person} size={size} className="avatar-stacked" />
      ))}
      {extra > 0 ? (
        <span
          className="avatar avatar-stacked avatar-more"
          style={{ width: size, height: size, fontSize: Math.max(9, Math.round(size * 0.31)) }}
          aria-hidden="true"
        >
          +{extra}
        </span>
      ) : null}
    </span>
  );
}
