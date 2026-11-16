export type Movie = {
  id: string;
  title: string;
  year: number;
  runtime: number;
  genres: string[];
  director: string;
  writers: string[];
  cast: string[];
  language: string;
  tagline?: string;
  synopsis: string;
  description: string;
  poster: string;
  backdrop: string;
};

export type Person = {
  id: string;
  name: string;
  short: string;
  color: string;
};

export type GroupFilmStatus = "up-next" | "watched";

export type GroupFilm = {
  movieId: string;
  status: GroupFilmStatus;
  /** Person id -> score out of 10. */
  scores: Record<string, number>;
  addedBy: string;
  addedAt: string;
  watchedOn?: string;
};

export type Group = {
  id: string;
  name: string;
  description: string;
  members: Person[];
  films: GroupFilm[];
  watchlist: Movie[];
  nextNight?: string;
  lastNight?: { movie: Movie; date: string };
};

export type Stage = "waiting" | "playing" | "final" | "winner";
export type VoteChoice = "in" | "seen" | "out";

export type Reveal = {
  movieId: string;
  inCount: number;
  total: number;
  shortlisted: boolean;
};

export type Lobby = {
  id: string;
  groupId: string | null;
  groupName: string;
  privacy: "group" | "open";
  hostId: string;
  youId: string;
  players: Person[];
  ready: string[];
  stage: Stage;
  roundIndex: number;
  votes: Record<string, VoteChoice>;
  shortlist: string[];
  reveal: Reveal | null;
  picks: Record<string, string>;
  picksRevealed: boolean;
  winnerId: string | null;
  tie: boolean;
};

export const YOU = "alex";

export const people: Record<string, Person> = {
  alex: { id: "alex", name: "Alex Rivera", short: "AR", color: "#e7b45a" },
  maya: { id: "maya", name: "Maya Chen", short: "MC", color: "#9bb39a" },
  jonas: { id: "jonas", name: "Jonas Berg", short: "JB", color: "#8fa6bf" },
  priya: { id: "priya", name: "Priya Nair", short: "PN", color: "#d09a83" },
  sam: { id: "sam", name: "Sam Okafor", short: "SO", color: "#b3a3ce" },
  noah: { id: "noah", name: "Noah Williams", short: "NW", color: "#7fb3a6" },
};

const poster = (slug: string) => `/media/posters/${slug}.jpg`;
const backdrop = (slug: string) => `/media/backdrops/${slug}.jpg`;

export const movies: Record<string, Movie> = {
  "past-lives": {
    id: "past-lives",
    title: "Past Lives",
    year: 2023,
    runtime: 106,
    genres: ["Drama", "Romance"],
    director: "Celine Song",
    synopsis:
      "Two childhood friends reunite in New York two decades after their families emigrated, and confront the lives they didn't lead.",
    description:
      "Two childhood friends are separated after one's family emigrates from South Korea. Two decades later, they are reunited in New York for one week as they confront notions of destiny, love and the choices that make a life.",
    writers: ["Celine Song"],
    cast: ["Greta Lee", "Teo Yoo", "John Magaro"],
    language: "English, Korean",
    poster: poster("past-lives"),
    backdrop: backdrop("past-lives"),
  },
  oppenheimer: {
    id: "oppenheimer",
    title: "Oppenheimer",
    year: 2023,
    runtime: 181,
    genres: ["Drama", "History"],
    director: "Christopher Nolan",
    synopsis:
      "The story of J. Robert Oppenheimer's role in the development of the atomic bomb, and the weight of what came after.",
    tagline: "The world forever changes.",
    description:
      "The story of J. Robert Oppenheimer's role in the development of the atomic bomb during World War II.",
    writers: ["Christopher Nolan"],
    cast: ["Cillian Murphy", "Emily Blunt", "Robert Downey Jr.", "Matt Damon"],
    language: "English",
    poster: poster("oppenheimer"),
    backdrop: backdrop("oppenheimer"),
  },
  "grand-budapest": {
    id: "grand-budapest",
    title: "The Grand Budapest Hotel",
    year: 2014,
    runtime: 100,
    genres: ["Comedy", "Drama"],
    director: "Wes Anderson",
    synopsis:
      "A legendary concierge and his lobby boy become entangled in a stolen painting, a family fortune and a vanishing old world.",
    tagline: "A murder case of Madam D. With enormous wealth and the most outrageous events surrounding her sudden death!",
    description:
      "The Grand Budapest Hotel tells of a legendary concierge at a famous European hotel between the wars and his friendship with a young employee who becomes his trusted protégé. The story involves the theft and recovery of a priceless Renaissance painting, the battle for an enormous family fortune and the slow and then sudden upheavals that transformed Europe during the first half of the 20th century.",
    writers: ["Wes Anderson", "Hugo Guinness"],
    cast: ["Ralph Fiennes", "Tony Revolori", "F. Murray Abraham", "Saoirse Ronan"],
    language: "English, French",
    poster: poster("grand-budapest"),
    backdrop: backdrop("grand-budapest"),
  },
  "paddington-2": {
    id: "paddington-2",
    title: "Paddington 2",
    year: 2017,
    runtime: 104,
    genres: ["Adventure", "Comedy", "Family"],
    director: "Paul King",
    synopsis:
      "Paddington hunts for the perfect gift for his aunt, only to be framed for theft and sent to prison.",
    tagline: "It takes a bear to catch a thief.",
    description:
      "Paddington, now happily settled with the Browns, picks up a series of odd jobs to buy the perfect present for his Aunt Lucy, but it is stolen.",
    writers: ["Paul King", "Simon Farnaby"],
    cast: ["Ben Whishaw", "Hugh Bonneville", "Sally Hawkins", "Hugh Grant"],
    language: "English",
    poster: poster("paddington-2"),
    backdrop: backdrop("paddington-2"),
  },
  "anatomy-fall": {
    id: "anatomy-fall",
    title: "Anatomy of a Fall",
    year: 2023,
    runtime: 151,
    genres: ["Drama", "Crime", "Mystery"],
    director: "Justine Triet",
    synopsis:
      "A writer stands trial for her husband's death, and their blind son is the only witness.",
    tagline: "Did she do it?",
    description:
      "Sandra, Samuel and their visually impaired son Daniel have been living in a remote mountain location for the past year. When Samuel is found dead outside the house, an investigation for death in suspicious circumstances is launched. Amidst the uncertainty, Sandra is indicted: was it suicide or homicide? A year later Daniel attends his mother's trial, a veritable dissection of his parents' relationship.",
    writers: ["Justine Triet", "Arthur Harari"],
    cast: ["Sandra Hüller", "Swann Arlaud", "Milo Machado-Graner"],
    language: "French, English",
    poster: poster("anatomy-fall"),
    backdrop: backdrop("anatomy-fall"),
  },
  "boy-heron": {
    id: "boy-heron",
    title: "The Boy and the Heron",
    year: 2023,
    runtime: 124,
    genres: ["Animation", "Fantasy"],
    director: "Hayao Miyazaki",
    synopsis:
      "A grieving boy follows a grey heron into a world of the living and the dead.",
    description:
      "While the Second World War rages, the teenage Mahito, haunted by his mother's tragic death, is relocated from Tokyo to the serene rural home of his new stepmother Natsuko, a woman who bears a striking resemblance to the boy's mother. As he tries to adjust, this strange new world grows even stranger following the appearance of a persistent gray heron, who perplexes and bedevils Mahito, dubbing him the 'long-awaited one.'",
    writers: ["Hayao Miyazaki"],
    cast: ["Soma Santoki", "Masaki Suda", "Ko Shibasaki"],
    language: "Japanese",
    poster: poster("boy-heron"),
    backdrop: backdrop("boy-heron"),
  },
  "everything-everywhere": {
    id: "everything-everywhere",
    title: "Everything Everywhere All at Once",
    year: 2022,
    runtime: 140,
    genres: ["Action", "Adventure", "Sci-Fi"],
    director: "Daniels",
    synopsis:
      "A laundromat owner discovers she must connect with her parallel lives to stop a cosmic threat.",
    tagline: "The universe is so much bigger than you realize.",
    description:
      "An aging Chinese immigrant is swept up in an insane adventure, where she alone can save what's important to her by connecting with the lives she could have led in other universes.",
    writers: ["Daniel Kwan", "Daniel Scheinert"],
    cast: ["Michelle Yeoh", "Ke Huy Quan", "Stephanie Hsu", "Jamie Lee Curtis"],
    language: "English, Mandarin, Cantonese",
    poster: poster("everything-everywhere"),
    backdrop: backdrop("everything-everywhere"),
  },
  barbie: {
    id: "barbie",
    title: "Barbie",
    year: 2023,
    runtime: 114,
    genres: ["Comedy", "Fantasy"],
    director: "Greta Gerwig",
    synopsis:
      "Barbie leaves Barbieland for the real world and discovers what it means to be human.",
    tagline: "She's everything. He's just Ken.",
    description:
      "Barbie and Ken are having the time of their lives in the colorful and seemingly perfect world of Barbie Land. However, when they get a chance to go to the real world, they soon discover the joys and perils of living among humans.",
    writers: ["Greta Gerwig", "Noah Baumbach"],
    cast: ["Margot Robbie", "Ryan Gosling", "America Ferrera", "Kate McKinnon"],
    language: "English",
    poster: poster("barbie"),
    backdrop: backdrop("barbie"),
  },
  "spider-verse": {
    id: "spider-verse",
    title: "Spider-Man: Across the Spider-Verse",
    year: 2023,
    runtime: 140,
    genres: ["Animation", "Action"],
    director: "Joaquim Dos Santos",
    synopsis:
      "Miles Morales meets a team of Spider-People and clashes over how to save the multiverse.",
    tagline: "It's how you wear the mask that matters.",
    description:
      "After reuniting with Gwen Stacy, Brooklyn's full-time, friendly neighborhood Spider-Man is catapulted across the Multiverse, where he encounters the Spider Society, a team of Spider-People charged with protecting the Multiverse's very existence. But when the heroes clash on how to handle a new threat, Miles finds himself pitted against the other Spiders and must set out on his own to save those he loves most.",
    writers: ["Phil Lord", "Christopher Miller", "Dave Callaham"],
    cast: ["Shameik Moore", "Hailee Steinfeld", "Oscar Isaac", "Jake Johnson"],
    language: "English",
    poster: poster("spider-verse"),
    backdrop: backdrop("spider-verse"),
  },
};

export const allMovies = Object.values(movies);

function groupFilm(
  movieId: string,
  status: GroupFilmStatus,
  scores: Record<string, number>,
  addedBy: string,
  addedAt: string,
  watchedOn?: string,
): GroupFilm {
  return { movieId, status, scores, addedBy, addedAt, watchedOn };
}

function makeGroup(
  input: Omit<Group, "watchlist">,
): Group {
  const watchlist = input.films
    .map((film) => movies[film.movieId])
    .filter((movie): movie is Movie => Boolean(movie));
  return { ...input, watchlist };
}

export const initialGroups: Group[] = [
  makeGroup({
    id: "friday",
    name: "Friday Film Club",
    description: "A standing Friday date with good films and questionable wine.",
    members: [people.alex, people.maya, people.jonas, people.priya, people.sam],
    nextNight: "Fri 30 Oct",
    films: [
      groupFilm(
        "spider-verse",
        "watched",
        { alex: 8.6, maya: 8.4, jonas: 8.8, priya: 8.2, sam: 8.6 },
        "jonas",
        "1 Oct",
        "Fri 9 Oct",
      ),
      groupFilm("grand-budapest", "up-next", {}, "alex", "9 Oct"),
      groupFilm(
        "paddington-2",
        "watched",
        { alex: 9.3, maya: 9.0, jonas: 8.8, priya: 9.4, sam: 9.0 },
        "priya",
        "20 Sep",
        "Fri 23 Oct",
      ),
      groupFilm(
        "oppenheimer",
        "watched",
        { alex: 8.6, maya: 8.0, jonas: 8.4, priya: 7.8, sam: 8.2 },
        "jonas",
        "28 Sep",
        "Sat 17 Oct",
      ),
      groupFilm("anatomy-fall", "up-next", {}, "sam", "11 Oct"),
      groupFilm("boy-heron", "up-next", {}, "maya", "12 Oct"),
    ],
    lastNight: { movie: movies["paddington-2"], date: "Fri 23 Oct" },
  }),
  makeGroup({
    id: "slow-burn",
    name: "The Slow Burn Society",
    description: "Long films, longer debates. No phones at the table.",
    members: [people.alex, people.maya, people.jonas, people.priya],
    nextNight: "Sat 31 Oct",
    films: [
      groupFilm(
        "anatomy-fall",
        "watched",
        { alex: 7.8, maya: 8.1, jonas: 7.6, priya: 8.1 },
        "maya",
        "18 Sep",
        "Sat 17 Oct",
      ),
      groupFilm(
        "oppenheimer",
        "watched",
        { alex: 8.4, maya: 8.0, jonas: 8.3, priya: 8.1 },
        "jonas",
        "28 Sep",
        "Sat 17 Oct",
      ),
      groupFilm("boy-heron", "up-next", {}, "alex", "12 Oct"),
      groupFilm("past-lives", "up-next", {}, "priya", "10 Oct"),
    ],
    lastNight: { movie: movies["anatomy-fall"], date: "Sat 17 Oct" },
  }),
  makeGroup({
    id: "letterboxd",
    name: "Letterboxd Refugees",
    description: "We log everything. Even the bad ones.",
    members: [people.alex, people.maya, people.jonas, people.priya, people.sam, people.noah],
    nextNight: "Fri 30 Oct",
    films: [
      groupFilm(
        "everything-everywhere",
        "watched",
        { alex: 9.2, maya: 9.0, jonas: 8.8, priya: 9.1, sam: 9.2, noah: 8.7 },
        "sam",
        "5 Oct",
        "Fri 9 Oct",
      ),
      groupFilm("barbie", "up-next", {}, "priya", "14 Oct"),
      groupFilm(
        "spider-verse",
        "watched",
        { alex: 8.6, maya: 8.4, jonas: 8.8, priya: 8.2, sam: 8.6, noah: 8.4 },
        "jonas",
        "1 Oct",
        "Fri 9 Oct",
      ),
      groupFilm(
        "paddington-2",
        "watched",
        { alex: 9.3, maya: 9.0, jonas: 8.8, priya: 9.4, sam: 9.0, noah: 9.1 },
        "maya",
        "20 Sep",
        "Fri 25 Sep",
      ),
      groupFilm("grand-budapest", "up-next", {}, "alex", "16 Oct"),
      groupFilm(
        "past-lives",
        "watched",
        { alex: 9.0, maya: 9.2, jonas: 8.4, priya: 8.9, sam: 8.5, noah: 8.6 },
        "maya",
        "2 Oct",
        "Fri 2 Oct",
      ),
      groupFilm("boy-heron", "up-next", {}, "noah", "18 Oct"),
    ],
    lastNight: { movie: movies["everything-everywhere"], date: "Fri 9 Oct" },
  }),
];

export const recentNights = [
  {
    id: "night-1",
    movie: movies["paddington-2"],
    groupId: "friday",
    group: "Friday Film Club",
    date: "Fri 23 Oct",
    rating: 9.1,
    note: "The rare sequel that earns the tears. Nine of ten, no notes.",
  },
  {
    id: "night-2",
    movie: movies["anatomy-fall"],
    groupId: "slow-burn",
    group: "The Slow Burn Society",
    date: "Sat 17 Oct",
    rating: 7.9,
    note: "Half the club thinks she did it. The other half wants to rewatch the dog.",
  },
  {
    id: "night-3",
    movie: movies["everything-everywhere"],
    groupId: "letterboxd",
    group: "Letterboxd Refugees",
    date: "Fri 9 Oct",
    rating: 9.0,
    note: "A laundry, a bagel, a rock. The room laughed, then went very quiet.",
  },
];

export type RecentNight = (typeof recentNights)[number];

export const PLAY_ORDER = ["past-lives", "oppenheimer", "grand-budapest"];
export const DEMO_FINALISTS = ["past-lives", "grand-budapest"];
export const INVITE_CODE = "7f3k2";

export const invitePreview = {
  code: INVITE_CODE,
  host: people.maya,
  title: "Open movie night",
  note: "Maya is hosting an open movie night. Anyone with the link can join — the room is not listed publicly.",
  players: [people.maya, people.jonas, people.priya, people.sam],
};

export function movieById(id: string | null | undefined): Movie | null {
  return id ? (movies[id] ?? null) : null;
}

export function crowdVote(playerId: string, movieId: string): VoteChoice {
  if (movieId === "oppenheimer") {
    if (playerId === "priya") return "out";
    if (playerId === "jonas") return "seen";
  }
  return "in";
}

export function crowdPick(playerId: string, finalistIds: string[]): string {
  if (!finalistIds.length) return "";
  if (playerId === "maya" || playerId === "priya" || playerId === "noah") {
    if (finalistIds.includes("past-lives")) return "past-lives";
  }
  if (playerId === "jonas" || playerId === "sam") {
    if (finalistIds.includes("grand-budapest")) return "grand-budapest";
  }
  return finalistIds[0];
}

export function makeLobby(
  group: Group | null,
  open = false,
  host: Person = people.alex,
): Lobby {
  const players = open
    ? [host, people.maya, people.jonas, people.priya, people.sam].filter(
        (person, index, list) => list.findIndex((entry) => entry.id === person.id) === index,
      )
    : (group?.members ?? [host]);

  const ready = players
    .filter((person) => person.id !== host.id)
    .map((person) => person.id);

  return {
    id: "friday",
    groupId: group?.id ?? null,
    groupName: open ? "Open movie night" : (group?.name ?? "Movie night"),
    privacy: open ? "open" : "group",
    hostId: host.id,
    youId: host.id,
    players,
    ready,
    stage: "waiting",
    roundIndex: 0,
    votes: {},
    shortlist: [],
    reveal: null,
    picks: {},
    picksRevealed: false,
    winnerId: null,
    tie: false,
  };
}

export function makeJoinLobby(guest?: Person): Lobby {
  const player = guest ?? people.alex;
  return {
    ...makeLobby(null, true, people.maya),
    groupId: null,
    groupName: "Open movie night",
    privacy: "open",
    hostId: "maya",
    youId: player.id,
    players: [people.maya, people.jonas, people.priya, people.sam, player],
    ready: ["maya", "jonas", "priya"],
  };
}

export function makeDemoLobby(stage: Stage): Lobby {
  const base = makeLobby(initialGroups[0]);
  const everyone = base.players.map((person) => person.id);

  if (stage === "waiting") return base;

  if (stage === "playing") {
    return { ...base, stage, ready: everyone };
  }

  if (stage === "final") {
    return {
      ...base,
      stage,
      ready: everyone,
      shortlist: [...DEMO_FINALISTS],
    };
  }

  return {
    ...base,
    stage,
    ready: everyone,
    shortlist: [...DEMO_FINALISTS],
    picks: {
      alex: "past-lives",
      maya: "past-lives",
      jonas: "grand-budapest",
      priya: "past-lives",
      sam: "grand-budapest",
    },
    picksRevealed: true,
    winnerId: "past-lives",
  };
}

export function stageLabel(lobby: Lobby): string {
  switch (lobby.stage) {
    case "waiting":
      return `Waiting room · ${lobby.ready.length} of ${lobby.players.length} ready`;
    case "playing":
      return `Voting · film ${lobby.roundIndex + 1} of ${PLAY_ORDER.length}`;
    case "final":
      return `The shortlist · ${lobby.shortlist.length} ${lobby.shortlist.length === 1 ? "film" : "films"}`;
    case "winner":
      return "Tonight's pick";
  }
}

export function winnerCounts(lobby: Lobby): Array<{ movieId: string; count: number }> {
  return lobby.shortlist
    .map((movieId) => ({
      movieId,
      count: Object.values(lobby.picks).filter((pick) => pick === movieId).length,
    }))
    .sort((a, b) => b.count - a.count || lobby.shortlist.indexOf(a.movieId) - lobby.shortlist.indexOf(b.movieId));
}
