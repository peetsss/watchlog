import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  PLAY_ORDER,
  YOU,
  crowdPick,
  crowdVote,
  makeDemoLobby,
  makeJoinLobby,
  makeLobby,
  winnerCounts,
  type Group,
  type Lobby,
  type Person,
  type Stage,
  type VoteChoice,
} from "../data";

type LobbyContextValue = {
  lobby: Lobby | null;
  startLobby: (group: Group | null, open?: boolean, host?: Person | null) => Lobby;
  joinOpenLobby: (guest?: Person | null) => Lobby;
  setReady: (playerId: string, ready: boolean) => void;
  startNight: () => void;
  vote: (choice: VoteChoice) => void;
  nextFilm: () => void;
  pick: (movieId: string) => void;
  revealWinner: () => void;
  restartNight: () => void;
  resetLobby: () => void;
};

const LobbyContext = createContext<LobbyContextValue | null>(null);
const STORAGE_KEY = "watchlog.prototype.lobby";
const STAGES: Stage[] = ["waiting", "playing", "final", "winner"];

function loadInitialLobby(): Lobby | null {
  const stage = new URLSearchParams(window.location.search).get("stage");
  if (window.location.pathname.startsWith("/lobby/") && stage && STAGES.includes(stage as Stage)) {
    return makeDemoLobby(stage as Stage);
  }

  try {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as Lobby;
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !Array.isArray(parsed.players) ||
      !STAGES.includes(parsed.stage as Stage)
    ) {
      return null;
    }
    return { ...parsed, youId: parsed.youId ?? YOU };
  } catch {
    return null;
  }
}

export function LobbyProvider({ children }: { children: ReactNode }) {
  const [lobby, setLobby] = useState<Lobby | null>(loadInitialLobby);

  useEffect(() => {
    try {
      if (lobby) {
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lobby));
      } else {
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Session storage can be unavailable in private browsing; the flow still works.
    }
  }, [lobby]);

  const startLobby = useCallback((group: Group | null, open = false, host?: Person | null) => {
    const next = makeLobby(group, open, host ?? undefined);
    setLobby(next);
    return next;
  }, []);

  const joinOpenLobby = useCallback((guest?: Person | null) => {
    const next = makeJoinLobby(guest ?? undefined);
    setLobby(next);
    return next;
  }, []);

  const setReady = useCallback((playerId: string, ready: boolean) => {
    setLobby((current) => {
      if (!current || current.stage !== "waiting") return current;
      const nextReady = ready
        ? Array.from(new Set([...current.ready, playerId]))
        : current.ready.filter((id) => id !== playerId);
      return { ...current, ready: nextReady };
    });
  }, []);

  const startNight = useCallback(() => {
    setLobby((current) => {
      if (!current || current.stage !== "waiting") return current;
      return {
        ...current,
        stage: "playing",
        roundIndex: 0,
        votes: {},
        shortlist: [],
        reveal: null,
        picks: {},
        picksRevealed: false,
        winnerId: null,
        tie: false,
      };
    });
  }, []);

  const vote = useCallback((choice: VoteChoice) => {
    setLobby((current) => {
      if (!current || current.stage !== "playing" || current.reveal) return current;
      const movieId = PLAY_ORDER[current.roundIndex];
      if (!movieId || current.votes[movieId]) return current;
      return { ...current, votes: { ...current.votes, [movieId]: choice } };
    });
  }, []);

  const nextFilm = useCallback(() => {
    setLobby((current) => {
      if (!current || current.stage !== "playing" || !current.reveal) return current;
      if (current.roundIndex >= PLAY_ORDER.length - 1) {
        return { ...current, stage: "final", reveal: null };
      }
      return { ...current, roundIndex: current.roundIndex + 1, reveal: null };
    });
  }, []);

  const pick = useCallback((movieId: string) => {
    setLobby((current) => {
      if (
        !current ||
        current.stage !== "final" ||
        current.picks[current.youId] ||
        !current.shortlist.includes(movieId)
      ) {
        return current;
      }
      return {
        ...current,
        picks: { ...current.picks, [current.youId]: movieId },
        picksRevealed: false,
      };
    });
  }, []);

  const revealWinner = useCallback(() => {
    setLobby((current) => {
      if (!current || current.stage !== "final" || !current.picksRevealed) return current;
      const counts = winnerCounts(current);
      const winnerId = counts[0]?.movieId ?? null;
      const tie = counts.length > 1 && counts[0].count === counts[1].count;
      return { ...current, stage: "winner", winnerId, tie };
    });
  }, []);

  const restartNight = useCallback(() => {
    setLobby((current) => {
      if (!current) return current;
      return {
        ...current,
        stage: "waiting",
        ready: current.players
          .filter((person) => person.id !== current.youId)
          .map((person) => person.id),
        roundIndex: 0,
        votes: {},
        shortlist: [],
        reveal: null,
        picks: {},
        picksRevealed: false,
        winnerId: null,
        tie: false,
      };
    });
  }, []);

  const resetLobby = useCallback(() => setLobby(null), []);

  // Resolve the room after your vote, including after a refresh mid-vote.
  useEffect(() => {
    if (!lobby || lobby.stage !== "playing" || lobby.reveal) return;
    const movieId = PLAY_ORDER[lobby.roundIndex];
    if (!movieId || !lobby.votes[movieId]) return;

    const id = window.setTimeout(() => {
      setLobby((current) => {
        if (!current || current.stage !== "playing" || current.reveal) return current;
        if (PLAY_ORDER[current.roundIndex] !== movieId) return current;
        const mine = current.votes[movieId];
        if (!mine) return current;

        const ballot = Object.fromEntries(
          current.players.map((person) => [
            person.id,
            person.id === current.youId ? mine : crowdVote(person.id, movieId),
          ]),
        ) as Record<string, VoteChoice>;

        const inCount = Object.values(ballot).filter((value) => value === "in").length;
        const shortlisted = inCount === current.players.length;

        return {
          ...current,
          reveal: { movieId, inCount, total: current.players.length, shortlisted },
          shortlist: shortlisted
            ? Array.from(new Set([...current.shortlist, movieId]))
            : current.shortlist,
        };
      });
    }, 1250);

    return () => window.clearTimeout(id);
  }, [lobby]);

  // Resolve the room after your final pick, including after a refresh.
  useEffect(() => {
    if (
      !lobby ||
      lobby.stage !== "final" ||
      lobby.picksRevealed ||
      !lobby.picks[lobby.youId]
    ) {
      return;
    }

    const id = window.setTimeout(() => {
      setLobby((current) => {
        if (!current || current.stage !== "final" || current.picksRevealed) return current;
        if (!current.picks[current.youId]) return current;

        const picks = { ...current.picks };
        for (const person of current.players) {
          if (person.id !== current.youId) {
            picks[person.id] = crowdPick(person.id, current.shortlist);
          }
        }
        return { ...current, picks, picksRevealed: true };
      });
    }, 1250);

    return () => window.clearTimeout(id);
  }, [lobby]);

  const isGuest = Boolean(lobby && lobby.hostId !== lobby.youId);
  const allReady = Boolean(lobby && lobby.players.every((person) => lobby.ready.includes(person.id)));

  useEffect(() => {
    if (!lobby || lobby.stage !== "waiting" || !isGuest) return;
    if (!lobby.ready.includes(lobby.youId)) return;
    if (!lobby.players.some((person) => person.id === "sam") || lobby.ready.includes("sam")) return;

    const id = window.setTimeout(() => setReady("sam", true), 900);
    return () => window.clearTimeout(id);
  }, [lobby, isGuest, setReady]);

  useEffect(() => {
    if (!lobby || lobby.stage !== "waiting" || !isGuest || !allReady) return;
    const id = window.setTimeout(() => startNight(), 1450);
    return () => window.clearTimeout(id);
  }, [lobby, isGuest, allReady, startNight]);

  return (
    <LobbyContext.Provider
      value={{
        lobby,
        startLobby,
        joinOpenLobby,
        setReady,
        startNight,
        vote,
        nextFilm,
        pick,
        revealWinner,
        restartNight,
        resetLobby,
      }}
    >
      {children}
    </LobbyContext.Provider>
  );
}

export function useLobby() {
  const context = useContext(LobbyContext);
  if (!context) throw new Error("useLobby must be used within LobbyProvider");
  return context;
}
