import { Link } from "react-router-dom";
import { cx } from "../lib/cx";

export function LegalLinks({ className }: { className?: string }) {
  return (
    <nav className={cx("legal-links", className)} aria-label="Legal and credits">
      <span className="legal-links-nav">
        <Link to="/about">About &amp; credits</Link>
        <span aria-hidden="true">·</span>
        <Link to="/privacy">Privacy</Link>
        <span aria-hidden="true">·</span>
        <Link to="/terms">Terms</Link>
      </span>
      <span className="legal-data-note">Data from TMDB · Watch options by JustWatch</span>
    </nav>
  );
}
