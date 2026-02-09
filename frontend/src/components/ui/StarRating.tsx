import { Star } from "lucide-react";

interface StarRatingProps {
  rating: number;
  maxStars?: number;
  size?: number;
}

export default function StarRating({
  rating,
  maxStars = 5,
  size = 16,
}: StarRatingProps) {
  return (
    <div className="flex gap-1" data-testid="star-rating">
      {Array.from({ length: maxStars }, (_, i) => (
        <Star
          key={i}
          data-testid={`star-${i}`}
          size={size}
          fill={i < rating ? "#FF6B35" : "none"}
          stroke={i < rating ? "#FF6B35" : "#666"}
        />
      ))}
    </div>
  );
}
