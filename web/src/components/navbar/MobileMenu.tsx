import { Menu, Search } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useSearch } from "@/contexts/SearchContext";

interface NavLinkItem {
  label: string;
  href: string;
}

const mainLinks: NavLinkItem[] = [
  { label: "Documentation", href: "/docs/overview" },
  { label: "Reference", href: "/api/search-packages" },
  { label: "Playground", href: "/playground" },
  { label: "Community", href: "/community" },
  { label: "Changelog", href: "/changelog" },
];


const MobileMenu = () => {
  const location = useLocation();
  const { openSearch } = useSearch();

  const isActive = (href: string) => {
    if (href.startsWith("/docs")) return location.pathname.startsWith("/docs");
    if (href.startsWith("/api")) return location.pathname.startsWith("/api");
    return location.pathname === href;
  };

  return (
    <div className="lg:hidden flex items-center gap-2">
      {/* Search Button */}
      <button
        onClick={openSearch}
        className="flex items-center justify-center w-10 h-10 rounded-xl border border-border text-muted-foreground transition-colors hover:text-foreground hover:border-muted-foreground/50"
        aria-label="Search"
      >
        <Search className="w-5 h-5" />
      </button>

      {/* Mobile Menu */}
      <Sheet>
        <SheetTrigger asChild>
          <button
            className="flex items-center justify-center w-10 h-10 rounded-xl border border-border text-muted-foreground transition-colors hover:text-foreground hover:border-muted-foreground/50"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        </SheetTrigger>
        <SheetContent side="right" className="w-[300px] bg-background border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">Menu</SheetTitle>
          </SheetHeader>
          <nav className="flex flex-col gap-2 mt-8">
            {/* Main Navigation Links */}
            {mainLinks.map((link) => (
              <Link
                key={link.label}
                to={link.href}
                className={`px-4 py-3 text-base font-medium rounded-xl transition-colors ${
                  isActive(link.href)
                    ? "text-foreground bg-secondary"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                }`}
              >
                {link.label}
              </Link>
            ))}

            {/* GitHub Link */}
            <a
              href="https://github.com/Sotlas/sotlas"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-3 text-base font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/50 rounded-xl transition-colors"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              <span>GitHub</span>
            </a>
          </nav>
        </SheetContent>
      </Sheet>
    </div>
  );
};

export default MobileMenu;
