import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, FileText, Code, Clock, ArrowRight } from "lucide-react";
import { useSearch } from "@/contexts/SearchContext";
import { useDebounce } from "@/hooks/use-debounce";
import { useSearchResults, type SearchResult } from "@/hooks/use-search-results";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

const categoryLabels = {
  docs: "Documentation",
  api: "API Reference",
  changelog: "Changelog",
};

const categoryIcons = {
  docs: FileText,
  api: Code,
  changelog: Clock,
};

const SearchModal = () => {
  const { isOpen, closeSearch } = useSearch();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const results = useSearchResults(debouncedQuery);

  // Reset query when modal closes
  useEffect(() => {
    if (!isOpen) {
      setQuery("");
    }
  }, [isOpen]);

  const handleSelect = (result: SearchResult) => {
    closeSearch();
    navigate(result.href);
  };

  // Group results by category
  const groupedResults = results.reduce((acc, result) => {
    if (!acc[result.category]) {
      acc[result.category] = [];
    }
    acc[result.category].push(result);
    return acc;
  }, {} as Record<string, SearchResult[]>);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 md:pt-32">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeSearch}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15 }}
            className="relative z-10 w-full max-w-[600px] mx-4"
          >
            <Command className="rounded-xl border border-border bg-background shadow-2xl overflow-hidden">
              <div className="flex items-center border-b border-border px-4">
                <Search className="mr-3 h-4 w-4 shrink-0 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search documentation..."
                  className="flex h-14 w-full bg-transparent py-3 text-sm text-foreground placeholder:text-muted-foreground outline-none"
                  autoFocus
                />
                <kbd className="ml-2 hidden sm:flex items-center justify-center h-6 px-2 rounded bg-secondary text-xs font-medium text-muted-foreground">
                  ESC
                </kbd>
              </div>

              <CommandList className="max-h-[400px] overflow-y-auto p-2">
                {debouncedQuery.length >= 2 && results.length === 0 && (
                  <div className="py-12 text-center">
                    <p className="text-sm text-muted-foreground">
                      No results found for "{debouncedQuery}"
                    </p>
                  </div>
                )}

                {debouncedQuery.length < 2 && (
                  <div className="py-12 text-center">
                    <p className="text-sm text-muted-foreground">
                      Type at least 2 characters to search...
                    </p>
                  </div>
                )}

                {Object.entries(groupedResults).map(([category, items]) => {
                  const Icon = categoryIcons[category as keyof typeof categoryIcons];
                  return (
                    <CommandGroup
                      key={category}
                      heading={categoryLabels[category as keyof typeof categoryLabels]}
                      className="[&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:py-2"
                    >
                      {items.map((result) => (
                        <CommandItem
                          key={result.id}
                          value={result.id}
                          onSelect={() => handleSelect(result)}
                          className="group flex items-center gap-3 px-3 py-3 cursor-pointer rounded-lg data-[selected=true]:bg-accent"
                        >
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-secondary text-muted-foreground group-data-[selected=true]:bg-primary/10 group-data-[selected=true]:text-primary">
                            <Icon className="h-4 w-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">
                              {result.title}
                            </p>
                            <p className="text-xs text-muted-foreground truncate">
                              {result.description}
                            </p>
                          </div>
                          <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 group-data-[selected=true]:opacity-100 transition-opacity" />
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  );
                })}
              </CommandList>

              {results.length > 0 && (
                <div className="border-t border-border px-4 py-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    {results.length} result{results.length !== 1 ? "s" : ""}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1">
                      <kbd className="px-1.5 py-0.5 rounded bg-secondary font-mono">↑↓</kbd>
                      navigate
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="px-1.5 py-0.5 rounded bg-secondary font-mono">↵</kbd>
                      select
                    </span>
                  </div>
                </div>
              )}
            </Command>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default SearchModal;
