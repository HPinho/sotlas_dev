import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import type { NavItem } from "@/data/documentation";

interface DocSidebarItemProps {
  item: NavItem;
}

export function DocSidebarItem({ item }: DocSidebarItemProps) {
  const location = useLocation();
  const isActive = location.pathname === item.href;
  const Icon = item.icon;

  return (
    <Link
      to={item.href}
      className={cn(
        "relative flex items-center gap-2.5 pl-5 pr-2 py-1.5 text-sm transition-colors rounded-lg",
        isActive
          ? "text-foreground font-semibold bg-accent/30"
          : "text-muted-foreground hover:text-foreground hover:bg-accent/15"
      )}
    >
      {/* Active indicator overlaying the continuous line */}
      {isActive && (
        <div className="absolute left-2.5 top-1 bottom-1 w-0.5 rounded-full bg-primary" />
      )}
      <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground")} />
      <span className="flex-1 min-w-0 truncate text-xs md:text-sm">{item.title}</span>
      {item.isNew && (
        <span className="ml-2 shrink-0 inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-orange-500/15 text-orange-400 border border-orange-500/30">
          New
        </span>
      )}
    </Link>
  );
}
