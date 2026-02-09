import type { Movie, FriendActivity, Group, UserStat, Achievement } from "@/types";

export const trendingMovies: Movie[] = [
  {
    id: 1,
    title: "Dune: Part Two",
    year: 2024,
    rating: 4.5,
    poster: "linear-gradient(135deg, #FF6B35 0%, #F7931E 100%)",
    genre: "Sci-Fi",
  },
  {
    id: 2,
    title: "Past Lives",
    year: 2023,
    rating: 4.8,
    poster: "linear-gradient(135deg, #4ECDC4 0%, #44A08D 100%)",
    genre: "Drama",
  },
  {
    id: 3,
    title: "The Holdovers",
    year: 2023,
    rating: 4.3,
    poster: "linear-gradient(135deg, #C94B4B 0%, #4B134F 100%)",
    genre: "Comedy",
  },
  {
    id: 4,
    title: "Oppenheimer",
    year: 2023,
    rating: 4.7,
    poster: "linear-gradient(135deg, #000000 0%, #434343 100%)",
    genre: "Biography",
  },
];

export const friendActivity: FriendActivity[] = [
  {
    user: "Sarah M.",
    action: "rated",
    title: "Poor Things",
    rating: 5,
    time: "2h ago",
  },
  {
    user: "Alex K.",
    action: "added to list",
    title: "The Zone of Interest",
    list: "Must Watch 2024",
    time: "5h ago",
  },
  {
    user: "Jordan P.",
    action: "reviewed",
    title: "Killers of the Flower Moon",
    rating: 4,
    time: "1d ago",
  },
];

export const myGroups: Group[] = [
  { name: "Criterion Crew", members: 12, active: true },
  { name: "Horror Heads", members: 8, active: false },
  { name: "Arthouse Archive", members: 15, active: false },
];

export const userStats: UserStat[] = [
  { label: "Watched", value: "247" },
  { label: "Rated", value: "189" },
  { label: "Lists", value: "12" },
  { label: "Reviews", value: "34" },
];

export const achievements: Achievement[] = [
  { icon: "\u{1F3AC}", name: "Cinephile" },
  { icon: "\u{1F31F}", name: "Critic" },
  { icon: "\u{1F4DA}", name: "Curator" },
  { icon: "\u{1F465}", name: "Social" },
  { icon: "\u{1F3AD}", name: "Genre Master" },
  { icon: "\u{1F3C6}", name: "Top Reviewer" },
];

export const discoverMovies: Movie[] = [
  {
    id: 5,
    title: "The Brutalist",
    year: 2024,
    rating: 4.6,
    poster: "linear-gradient(135deg, #2C3E50 0%, #4CA1AF 100%)",
    genre: "Drama",
  },
  {
    id: 6,
    title: "Anora",
    year: 2024,
    rating: 4.4,
    poster: "linear-gradient(135deg, #E44D26 0%, #F16529 100%)",
    genre: "Drama",
  },
  {
    id: 7,
    title: "The Substance",
    year: 2024,
    rating: 4.1,
    poster: "linear-gradient(135deg, #8E2DE2 0%, #4A00E0 100%)",
    genre: "Horror",
  },
  {
    id: 8,
    title: "Conclave",
    year: 2024,
    rating: 4.3,
    poster: "linear-gradient(135deg, #B79891 0%, #94716B 100%)",
    genre: "Thriller",
  },
  {
    id: 9,
    title: "Nosferatu",
    year: 2024,
    rating: 4.2,
    poster: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
    genre: "Horror",
  },
  {
    id: 10,
    title: "A Real Pain",
    year: 2024,
    rating: 4.0,
    poster: "linear-gradient(135deg, #56ab2f 0%, #a8e063 100%)",
    genre: "Comedy",
  },
  {
    id: 11,
    title: "Emilia P\u00E9rez",
    year: 2024,
    rating: 3.8,
    poster: "linear-gradient(135deg, #f12711 0%, #f5af19 100%)",
    genre: "Musical",
  },
  {
    id: 12,
    title: "September 5",
    year: 2024,
    rating: 4.1,
    poster: "linear-gradient(135deg, #373B44 0%, #4286f4 100%)",
    genre: "Thriller",
  },
];

export const allGroups: Group[] = [
  { name: "Criterion Crew", members: 12, active: true },
  { name: "Horror Heads", members: 8, active: false },
  { name: "Arthouse Archive", members: 15, active: false },
  { name: "Sci-Fi Society", members: 23, active: true },
  { name: "Documentary Club", members: 6, active: false },
  { name: "Weekend Binge", members: 19, active: true },
];

export interface UserList {
  id: number;
  name: string;
  movieCount: number;
  description: string;
  gradient: string;
}

export const userLists: UserList[] = [
  {
    id: 1,
    name: "Must Watch 2024",
    movieCount: 24,
    description: "Essential films from this year",
    gradient: "linear-gradient(135deg, #FF6B35 0%, #F7931E 100%)",
  },
  {
    id: 2,
    name: "All-Time Favorites",
    movieCount: 47,
    description: "The best of the best",
    gradient: "linear-gradient(135deg, #4ECDC4 0%, #44A08D 100%)",
  },
  {
    id: 3,
    name: "Hidden Gems",
    movieCount: 18,
    description: "Underrated masterpieces",
    gradient: "linear-gradient(135deg, #C94B4B 0%, #4B134F 100%)",
  },
  {
    id: 4,
    name: "Weekend Comfort",
    movieCount: 31,
    description: "Easy watches for lazy days",
    gradient: "linear-gradient(135deg, #2C3E50 0%, #4CA1AF 100%)",
  },
];
