import { Link } from "react-router-dom";
import { cx } from "../lib/cx";

export function Wordmark({ className }: { className?: string }) {
  return (
    <Link to="/" className={cx("wordmark", className)} aria-label="watchlog home">
      <img className="wordmark-icon" src="/brand/watchlog-icon.svg?v=3" alt="" />
      <img className="wordmark-text" src="/brand/watchlog-wordmark.svg?v=3" alt="" />
    </Link>
  );
}
