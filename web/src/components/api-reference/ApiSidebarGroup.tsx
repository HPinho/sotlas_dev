import { ApiSidebarItem } from "./ApiSidebarItem";
import type { ApiGroup } from "@/data/api-reference";

interface ApiSidebarGroupProps {
  group: ApiGroup;
}

export function ApiSidebarGroup({ group }: ApiSidebarGroupProps) {
  return (
    <div className="space-y-1">
      <h3 className="px-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
        {group.title}
      </h3>
      <div className="relative">
        {/* Continuous vertical line for the group */}
        <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-sidebar-border" />
        <div className="relative">
          {group.endpoints.map((endpoint) => (
            <ApiSidebarItem key={endpoint.id} endpoint={endpoint} />
          ))}
        </div>
      </div>
    </div>
  );
}
