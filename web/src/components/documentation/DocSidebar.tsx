import { useState } from "react";
import { Menu } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { DocSidebarGroup } from "./DocSidebarGroup";
import { navigationGroups } from "@/data/documentation";
import { cn } from "@/lib/utils";

interface DocSidebarProps {
  className?: string;
}

function SidebarContent() {
  return (
    <ScrollArea className="h-full py-6">
      <div className="space-y-6 pl-3 pr-4">
        {navigationGroups.map((group) => (
          <DocSidebarGroup key={group.id} group={group} />
        ))}
      </div>
    </ScrollArea>
  );
}

export function DocSidebar({ className }: DocSidebarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile trigger */}
      <div className="lg:hidden fixed top-20 left-4 z-40">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <button
              className="p-2 rounded-md bg-background border border-border hover:bg-secondary transition-colors cursor-pointer shadow-xs"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80 sm:w-96 p-0 bg-background border-sidebar-border">
            <SheetHeader className="p-4 border-b border-sidebar-border">
              <SheetTitle className="text-sm font-semibold">Documentation</SheetTitle>
            </SheetHeader>
            <SidebarContent />
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop sidebar with comfortable width for long titles and badges */}
      <aside
        className={cn(
          "hidden lg:block w-80 shrink-0 border-r border-sidebar-border bg-sidebar-background sticky top-16 h-[calc(100vh-4rem)]",
          className
        )}
      >
        <SidebarContent />
      </aside>
    </>
  );
}
