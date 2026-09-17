import { Search } from "lucide-react";
import { useSearch } from "@/contexts/SearchContext";

const SearchBar = () => {
  const { openSearch } = useSearch();

  return (
    <button
      onClick={openSearch}
      className="hidden lg:inline-flex bg-card hover:bg-accent/40 border border-border hover:border-primary/40 rounded-xl items-center justify-between py-1.5 pl-3.5 pr-2 w-[260px] gap-3 transition-all shadow-2xs cursor-pointer"
    >
      <div className="flex items-center gap-2 flex-1">
        <Search className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <span className="text-xs text-muted-foreground">
          Search documentation...
        </span>
      </div>
      
      <div className="flex items-center gap-1 flex-shrink-0">
        <kbd className="flex items-center justify-center w-5 h-5 rounded bg-muted border border-border text-[10px] font-semibold text-muted-foreground font-mono">
          ⌘
        </kbd>
        <kbd className="flex items-center justify-center w-5 h-5 rounded bg-muted border border-border text-[10px] font-semibold text-muted-foreground font-mono">
          K
        </kbd>
      </div>
    </button>
  );
};

export default SearchBar;
