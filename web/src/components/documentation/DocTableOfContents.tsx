import { List } from "lucide-react";
import { cn } from "@/lib/utils";
import { useActiveSection } from "@/hooks/use-active-section";
interface TableOfContentsItem {
  id: string;
  title: string;
  level: "h2" | "h3";
}

interface DocTableOfContentsProps {
  items: TableOfContentsItem[];
  className?: string;
}

export function DocTableOfContents({ items, className }: DocTableOfContentsProps) {
  const sectionIds = items.map((item) => item.id);
  const activeId = useActiveSection(sectionIds);

  const handleClick = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <aside
      className={cn(
        "hidden xl:block w-56 shrink-0 sticky top-24 h-fit",
        className
      )}
    >
      <div className="flex items-center gap-2 text-sm font-semibold mb-4">
        <List className="h-4 w-4" />
        <span>On this page</span>
      </div>
      <nav className="relative">
        {/* Continuous vertical line */}
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-sidebar-border" />
        <div className="relative">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => handleClick(item.id)}
              className={cn(
                "relative block w-full text-left text-sm py-1.5 pl-4 transition-colors",
                item.level === "h3" ? "pl-6" : "pl-4",
                activeId === item.id
                  ? "text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {/* Active indicator overlaying the continuous line */}
              {activeId === item.id && (
                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-sidebar-primary" />
              )}
              {item.title}
            </button>
          ))}
        </div>
      </nav>
    </aside>
  );
}
