import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, X } from "lucide-react";
import {
  COOKIE_STORAGE_KEY,
  getStoredCookiePreferences,
  saveStoredCookiePreferences,
  CookiePreferences,
} from "./CookiePreferencesManager";

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(COOKIE_STORAGE_KEY);
      if (!stored) {
        // Small delay to prevent initial page layout jump
        const timer = setTimeout(() => setVisible(true), 1000);
        return () => clearTimeout(timer);
      }
    } catch {
      // ignore
    }
  }, []);

  const handleAcceptAll = () => {
    const prefs: CookiePreferences = {
      strictlyNecessary: true,
      functional: true,
      performance: true,
      updatedAt: new Date().toISOString(),
    };
    saveStoredCookiePreferences(prefs);
    setVisible(false);
  };

  const handleRejectNonEssential = () => {
    const prefs: CookiePreferences = {
      strictlyNecessary: true,
      functional: false,
      performance: false,
      updatedAt: new Date().toISOString(),
    };
    saveStoredCookiePreferences(prefs);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-8 md:max-w-md z-50 animate-in fade-in slide-in-from-bottom-5 duration-300">
      <div className="rounded-2xl border border-border bg-card/95 backdrop-blur-xl p-5 shadow-2xl space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 text-foreground font-semibold text-sm">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Privacy & Cookie Preferences</span>
          </div>
          <button
            type="button"
            onClick={handleRejectNonEssential}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg cursor-pointer"
            aria-label="Dismiss cookie banner"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          We use cookies and local storage to preserve developer settings, maintain security, and optimize compilation performance. We never sell data or use third-party tracking. Learn more in our{" "}
          <Link to="/privacy#cookies" className="text-primary hover:underline font-medium">
            Cookies Policy
          </Link>
          .
        </p>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            onClick={handleAcceptAll}
            className="px-3.5 py-1.5 rounded-xl bg-foreground text-background text-xs font-semibold hover:opacity-90 transition-opacity shadow-xs cursor-pointer"
          >
            Accept All
          </button>
          <button
            type="button"
            onClick={handleRejectNonEssential}
            className="px-3.5 py-1.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-xs font-medium transition-colors cursor-pointer"
          >
            Decline Non-Essential
          </button>
          <Link
            to="/privacy#cookies"
            onClick={() => setVisible(false)}
            className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors ml-auto font-medium"
          >
            Manage
          </Link>
        </div>
      </div>
    </div>
  );
}
