import { cn } from "@/lib/utils";

type BadgeVariant = "fixes" | "improvements" | "features";

interface ChangelogBadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  fixes: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  improvements: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  features: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

const ChangelogBadge = ({ variant, children }: ChangelogBadgeProps) => {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        variantStyles[variant]
      )}
    >
      {children}
    </span>
  );
};

export default ChangelogBadge;
