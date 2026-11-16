import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { YOU, initialGroups, people, type Group, type Movie, type Person } from "../data";

type GroupsContextValue = {
  groups: Group[];
  createGroup: (name: string, description: string, members?: Person[]) => Group;
  addMovieToGroup: (groupId: string, movie: Movie) => void;
  setGroupFilmScore: (groupId: string, movieId: string, score: number) => void;
};

const GroupsContext = createContext<GroupsContextValue | null>(null);

export function GroupsProvider({ children }: { children: ReactNode }) {
  const [groups, setGroups] = useState<Group[]>(initialGroups);

  const createGroup = useCallback((name: string, description: string, members: Person[] = [people.alex]) => {
    const group: Group = {
      id: `group-${Date.now()}`,
      name,
      description,
      members,
      films: [],
      watchlist: [],
      nextNight: "Friday",
    };
    setGroups((current) => [...current, group]);
    return group;
  }, []);

  const addMovieToGroup = useCallback((groupId: string, movie: Movie) => {
    setGroups((current) =>
      current.map((group) => {
        if (group.id !== groupId) return group;
        if (group.watchlist.some((entry) => entry.id === movie.id)) return group;
        return {
          ...group,
          films: [
            {
              movieId: movie.id,
              status: "up-next",
              scores: {},
              addedBy: YOU,
              addedAt: "Today",
            },
            ...group.films,
          ],
          watchlist: [movie, ...group.watchlist],
        };
      }),
    );
  }, []);

  const setGroupFilmScore = useCallback((groupId: string, movieId: string, score: number) => {
    setGroups((current) =>
      current.map((group) => {
        if (group.id !== groupId) return group;
        return {
          ...group,
          films: group.films.map((film) =>
            film.movieId === movieId
              ? {
                  ...film,
                  status: "watched",
                  watchedOn: film.watchedOn ?? "Tonight",
                  scores: { ...film.scores, [YOU]: score },
                }
              : film,
          ),
        };
      }),
    );
  }, []);

  return (
    <GroupsContext.Provider value={{ groups, createGroup, addMovieToGroup, setGroupFilmScore }}>
      {children}
    </GroupsContext.Provider>
  );
}

export function useGroups() {
  const context = useContext(GroupsContext);
  if (!context) throw new Error("useGroups must be used within GroupsProvider");
  return context;
}
