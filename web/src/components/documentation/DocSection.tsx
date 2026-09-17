import { cn } from "@/lib/utils";

interface DocSectionProps {
  id: string;
  title: string;
  level?: "h2" | "h3";
  children: React.ReactNode;
  className?: string;
}

export function DocSection({
  id,
  title,
  level = "h2",
  children,
  className,
}: DocSectionProps) {
  const HeadingTag = level;

  return (
    <section
      id={id}
      className={cn("scroll-mt-24", className)}
    >
      <HeadingTag
        className={cn(
          "font-semibold tracking-tight mb-4",
          level === "h2" ? "text-2xl" : "text-lg text-muted-foreground"
        )}
      >
        {title}
      </HeadingTag>
      <div className="text-muted-foreground leading-relaxed space-y-4">
        {children}
      </div>
    </section>
  );
}
