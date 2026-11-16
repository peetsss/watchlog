import { useEffect, useState } from "react";
import { Film } from "lucide-react";
import { cx } from "../lib/cx";

export function MoviePoster({
  src,
  title,
  className,
  iconSize = 22,
}: {
  src: string | null | undefined;
  title: string;
  className?: string;
  iconSize?: number;
}) {
  const [failed, setFailed] = useState(!src);

  useEffect(() => {
    setFailed(!src);
  }, [src]);

  if (failed || !src) {
    return (
      <span className={cx("movie-poster-fallback", className)} aria-hidden="true">
        <Film size={iconSize} />
      </span>
    );
  }

  return (
    <img
      className={className}
      src={src}
      alt={`${title} poster`}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
