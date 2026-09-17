import { cn } from "@/lib/utils";

interface ApiCodeBlockProps {
  children: string;
  className?: string;
}

export function ApiCodeBlock({ children, className }: ApiCodeBlockProps) {
  return (
    <pre
      className={cn(
        "bg-secondary/50 border border-border rounded-xl p-4 overflow-x-auto text-sm font-mono text-foreground scrollbar-none",
        className
      )}
    >
      <code>{children}</code>
    </pre>
  );
}
