import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { HttpMethodBadge } from "./HttpMethodBadge";
import type { ApiEndpoint } from "@/data/api-reference";

interface ApiSidebarItemProps {
  endpoint: ApiEndpoint;
}

export function ApiSidebarItem({ endpoint }: ApiSidebarItemProps) {
  const location = useLocation();
  const isActive = location.pathname === endpoint.href;

  return (
    <Link
      to={endpoint.href}
      className={cn(
        "relative flex items-center gap-3 pl-6 pr-3 py-2 text-sm transition-colors",
        isActive
          ? "text-foreground font-medium"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      {/* Active indicator overlaying the continuous line */}
      {isActive && (
        <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-sidebar-primary" />
      )}
      <HttpMethodBadge method={endpoint.method} />
      <span className="flex-1 min-w-0 truncate">{endpoint.title}</span>
    </Link>
  );
}
