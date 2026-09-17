import { HttpMethodBadge } from "./HttpMethodBadge";
import type { HttpMethod } from "@/data/api-reference";

interface ApiEndpointBlockProps {
  method: HttpMethod;
  path: string;
}

export function ApiEndpointBlock({ method, path }: ApiEndpointBlockProps) {
  return (
    <div className="flex items-center gap-4 bg-secondary/50 border border-border rounded-xl px-4 py-3">
      <HttpMethodBadge method={method} size="md" />
      <code className="text-sm font-mono text-foreground">{path}</code>
    </div>
  );
}
