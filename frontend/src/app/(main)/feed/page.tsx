import HeroSection from "@/components/feed/HeroSection";
import TrendingGrid from "@/components/feed/TrendingGrid";
import FriendActivityFeed from "@/components/feed/FriendActivityFeed";
import { trendingMovies, friendActivity } from "@/data/mock-data";

export default function FeedPage() {
  return (
    <div className="flex flex-col gap-12">
      <HeroSection movie={trendingMovies[0]} />
      <TrendingGrid movies={trendingMovies} />
      <FriendActivityFeed activities={friendActivity} />
    </div>
  );
}
