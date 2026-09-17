import { ChevronRight, Home } from "lucide-react";
import { Link } from "react-router-dom";

interface DocBreadcrumbProps {
  items: string[];
}

export function DocBreadcrumb({ items }: DocBreadcrumbProps) {
  return (
    <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
      <Link
        to="/docs"
        className="hover:text-foreground transition-colors flex items-center gap-1"
      >
        <Home className="h-4 w-4" />
        <span>Docs</span>
      </Link>
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <ChevronRight className="h-4 w-4" />
          <span
            className={
              index === items.length - 1
                ? "text-foreground font-medium"
                : "hover:text-foreground transition-colors cursor-pointer"
            }
          >
            {item}
          </span>
        </div>
      ))}
    </nav>
  );
}
