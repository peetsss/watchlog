interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "accent";
}

export default function Badge({ children, variant = "default" }: BadgeProps) {
  const base =
    "inline-flex items-center rounded-full px-3 py-1 text-xs font-heading tracking-wider";
  const variants = {
    default: "bg-black/70 backdrop-blur-[10px] text-text-primary",
    accent:
      "bg-accent-orange/10 border border-accent-orange/30 text-accent-orange",
  };

  return (
    <span className={`${base} ${variants[variant]}`} data-testid="badge">
      {children}
    </span>
  );
}
