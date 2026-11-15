import { Link } from "react-router-dom";
import { cx } from "../lib/cx";

export function Wordmark({ className }: { className?: string }) {
  return (
    <Link to="/" className={cx("wordmark", className)} aria-label="watchlog home">
      watchlog<span className="wordmark-dot">.</span>
    </Link>
  );
}
