import { ExternalLink } from "lucide-react";
import type { MovieDetailView } from "../lib/adapters";

function safeExternalUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function searchUrl(base: string, title: string): string {
  return `${base}${encodeURIComponent(title)}`;
}

type RatingSource = {
  label: string;
  value: string | null;
  url: string | null;
};

function movieRatingSources(movie: MovieDetailView): RatingSource[] {
  const imdbUrl =
    safeExternalUrl(movie.imdbUrl) ??
    (movie.imdbId
      ? `https://www.imdb.com/title/${movie.imdbId}`
      : searchUrl("https://www.imdb.com/find/?q=", movie.title));

  return [
    {
      label: "TMDB",
      value: movie.tmdbScore?.toFixed(1) ?? null,
      url: movie.tmdbId ? `https://www.themoviedb.org/movie/${movie.tmdbId}` : null,
    },
    { label: "IMDb", value: movie.imdbScore?.toFixed(1) ?? null, url: imdbUrl },
    {
      label: "RT",
      value: movie.rottentomatoScore,
      url:
        safeExternalUrl(movie.rottentomatoUrl) ??
        searchUrl("https://www.rottentomatoes.com/search?search=", movie.title),
    },
    {
      label: "Filmweb",
      value: movie.filmwebScore?.toFixed(1) ?? null,
      url:
        safeExternalUrl(movie.filmwebUrl) ??
        searchUrl("https://www.filmweb.pl/search?q=", movie.title),
    },
  ].filter((source) => source.value || source.url);
}

export function MovieRatings({ movie }: { movie: MovieDetailView }) {
  const sources = movieRatingSources(movie);
  if (!sources.length) return null;

  return (
    <section className="detail-section movie-ratings">
      <h3>Ratings & links</h3>
      <div className="movie-rating-line">
        {sources.map((source, index) => (
          <span className="movie-rating-item" key={source.label}>
            {index > 0 ? <span className="movie-rating-sep" aria-hidden="true">·</span> : null}
            {source.url ? (
              <a
                className="movie-rating-link"
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span>{source.label}</span>
                {source.value ? <strong>{source.value}</strong> : null}
                <ExternalLink size={10} aria-hidden="true" />
              </a>
            ) : (
              <span className="movie-rating-link">
                <span>{source.label}</span>
                {source.value ? <strong>{source.value}</strong> : null}
              </span>
            )}
          </span>
        ))}
      </div>
    </section>
  );
}
