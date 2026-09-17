import { Search } from "lucide-react";
import { useSearch } from "@/contexts/SearchContext";
import { useIsMobile } from "@/hooks/use-mobile";

const HeroSearchBar = () => {
  const { openSearch } = useSearch();
  const isMobile = useIsMobile();

  return (
    <button
      onClick={openSearch}
      className="bg-card hover:bg-accent/40 border border-border hover:border-primary/40 rounded-2xl inline-flex items-center justify-between py-3.5 pl-4 md:pl-6 pr-4 w-full max-w-[600px] gap-3 md:gap-5 transition-all shadow-xs hover:shadow-md cursor-pointer"
    >
      <div className="flex items-center gap-3 flex-1">
        <Search className="w-5 h-5 text-muted-foreground flex-shrink-0" />
        <span className="text-sm md:text-base text-muted-foreground">
          {isMobile ? "Search documentation..." : "Search docs (e.g. pointers, concurrency, SRG)..."}
        </span>
      </div>
      
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <kbd className="flex items-center justify-center w-6 h-6 rounded-md bg-muted border border-border text-xs font-semibold text-muted-foreground font-mono">
          ⌘
        </kbd>
        <kbd className="flex items-center justify-center w-6 h-6 rounded-md bg-muted border border-border text-xs font-semibold text-muted-foreground font-mono">
          K
        </kbd>
      </div>
    </button>
  );
};

export default HeroSearchBar;
