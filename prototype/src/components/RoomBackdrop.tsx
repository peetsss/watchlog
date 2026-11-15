import { cx } from "../lib/cx";

export function RoomBackdrop({ image, className }: { image?: string | null; className?: string }) {
  return (
    <div className={cx("room-backdrop", className)} aria-hidden="true">
      {image ? <div className="room-backdrop-image" style={{ backgroundImage: `url(${image})` }} /> : null}
      <div className="room-backdrop-scrim" />
    </div>
  );
}
