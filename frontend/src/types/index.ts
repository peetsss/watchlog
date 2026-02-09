export interface Movie {
  id: number;
  title: string;
  year: number;
  rating: number;
  poster: string;
  genre: string;
}

export interface FriendActivity {
  user: string;
  action: "rated" | "added to list" | "reviewed";
  title: string;
  rating?: number;
  list?: string;
  time: string;
}

export interface Group {
  name: string;
  members: number;
  active: boolean;
}

export interface UserStat {
  label: string;
  value: string;
}

export interface Achievement {
  icon: string;
  name: string;
}

export type NavTab = "feed" | "discover" | "groups" | "lists";
