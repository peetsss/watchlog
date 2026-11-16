import { movieById, type Group, type GroupFilm, type Movie, type Person } from "../../data";

export type ScoredMember = {
  person: Person;
  score: number;
};

export function movieForFilm(film: GroupFilm | null | undefined): Movie | null {
  return film ? movieById(film.movieId) : null;
}

export function scoredMembers(group: Group, film: GroupFilm): ScoredMember[] {
  return group.members
    .map((person) => ({ person, score: film.scores[person.id] }))
    .filter((entry): entry is ScoredMember => typeof entry.score === "number")
    .sort((a, b) => b.score - a.score || a.person.name.localeCompare(b.person.name));
}

export function filmAverage(group: Group, film: GroupFilm): number | null {
  const scored = scoredMembers(group, film);
  if (!scored.length) return null;
  return scored.reduce((sum, entry) => sum + entry.score, 0) / scored.length;
}

export function groupScoreSummary(group: Group): { average: number | null; count: number } {
  const scores = group.films.flatMap((film) =>
    group.members
      .map((person) => film.scores[person.id])
      .filter((score): score is number => typeof score === "number"),
  );
  if (!scores.length) return { average: null, count: 0 };
  return {
    average: scores.reduce((sum, score) => sum + score, 0) / scores.length,
    count: scores.length,
  };
}
