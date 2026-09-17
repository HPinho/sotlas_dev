import { cn } from "@/lib/utils";
import type { HttpMethod } from "@/data/api-reference";

interface HttpMethodBadgeProps {
  method: HttpMethod;
  size?: "sm" | "md";
}

const methodStyles: Record<HttpMethod, string> = {
  GET: "bg-emerald-500/20 text-emerald-400",
  POST: "bg-blue-500/20 text-blue-400",
  PUT: "bg-violet-500/20 text-violet-400",
  PATCH: "bg-orange-500/20 text-orange-400",
  DELETE: "bg-red-500/20 text-red-400",
};

export function HttpMethodBadge({ method, size = "sm" }: HttpMethodBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center font-mono font-semibold rounded uppercase",
        methodStyles[method],
        size === "sm" ? "text-[10px] px-1.5 py-0.5 min-w-[42px]" : "text-xs px-2 py-1"
      )}
    >
      {method}
    </span>
  );
}
