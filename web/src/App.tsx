import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SearchProvider } from "@/contexts/SearchContext";
import { SearchModal } from "@/components/search";
import { ThemeProvider } from "@/components/theme-provider";
import { CookieConsentBanner } from "@/components/cookie-manager/CookieConsentBanner";
import Index from "./pages/Index";
import Changelog from "./pages/Changelog";
import Documentation from "./pages/Documentation";
import ApiReference from "./pages/ApiReference";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import Playground from "./pages/Playground";
import Community from "./pages/Community";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="dark" forcedTheme="dark" enableSystem={false}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
        <SearchProvider>
          <SearchModal />
          <CookieConsentBanner />
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/changelog" element={<Changelog />} />
            <Route path="/docs/*" element={<Documentation />} />
            <Route path="/api/*" element={<ApiReference />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/privacy-policy" element={<PrivacyPolicy />} />
            <Route path="/playground" element={<Playground />} />
            <Route path="/community" element={<Community />} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </SearchProvider>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
