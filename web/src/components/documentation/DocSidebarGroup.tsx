import { DocSidebarItem } from "./DocSidebarItem";
import type { NavGroup } from "@/data/documentation";

interface DocSidebarGroupProps {
  group: NavGroup;
}

export function DocSidebarGroup({ group }: DocSidebarGroupProps) {
  return (
    <div>
      <h3 className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {group.title}
      </h3>
      <div className="relative mt-1">
        {/* Continuous vertical line */}
        <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-sidebar-border" />
        <div className="relative">
          {group.items.map((item) => (
            <DocSidebarItem key={item.id} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}
