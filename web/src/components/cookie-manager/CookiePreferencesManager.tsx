import { useState, useEffect } from "react";
import { ShieldCheck, Check, RotateCcw, Info, Lock, Settings2, Sliders } from "lucide-react";

export interface CookiePreferences {
  strictlyNecessary: boolean;
  functional: boolean;
  performance: boolean;
  updatedAt: string;
}

const DEFAULT_PREFS: CookiePreferences = {
  strictlyNecessary: true,
  functional: true,
  performance: false,
  updatedAt: new Date().toISOString(),
};

export const COOKIE_STORAGE_KEY = "sotlas_cookie_preferences";

export function getStoredCookiePreferences(): CookiePreferences {
  try {
    const raw = localStorage.getItem(COOKIE_STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (e) {
    console.error("Failed to parse cookie preferences:", e);
  }
  return DEFAULT_PREFS;
}

export function saveStoredCookiePreferences(prefs: CookiePreferences) {
  try {
    localStorage.setItem(COOKIE_STORAGE_KEY, JSON.stringify(prefs));
    window.dispatchEvent(new CustomEvent("sotlas-cookie-prefs-changed", { detail: prefs }));
  } catch (e) {
    console.error("Failed to save cookie preferences:", e);
  }
}

export function CookiePreferencesManager() {
  const [prefs, setPrefs] = useState<CookiePreferences>(DEFAULT_PREFS);
  const [savedFeedback, setSavedFeedback] = useState<string | null>(null);

  useEffect(() => {
    setPrefs(getStoredCookiePreferences());
  }, []);

  const handleSave = (customPrefs?: CookiePreferences, message = "Preferences saved successfully!") => {
    const toSave = customPrefs || prefs;
    const updated = { ...toSave, updatedAt: new Date().toISOString() };
    setPrefs(updated);
    saveStoredCookiePreferences(updated);
    setSavedFeedback(message);
    setTimeout(() => {
      setSavedFeedback(null);
    }, 4000);
  };

  const handleAcceptAll = () => {
    const allOn: CookiePreferences = {
      strictlyNecessary: true,
      functional: true,
      performance: true,
      updatedAt: new Date().toISOString(),
    };
    handleSave(allOn, "All cookies accepted!");
  };

  const handleRejectNonEssential = () => {
    const essentialOnly: CookiePreferences = {
      strictlyNecessary: true,
      functional: false,
      performance: false,
      updatedAt: new Date().toISOString(),
    };
    handleSave(essentialOnly, "Non-essential cookies disabled.");
  };

  const handleReset = () => {
    handleSave(DEFAULT_PREFS, "Reset to default preferences.");
  };

  return (
    <div className="rounded-3xl border border-border bg-card p-6 md:p-8 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2 text-primary font-mono text-xs mb-1">
            <Sliders className="w-4 h-4" />
            <span>Interactive Privacy Controls</span>
          </div>
          <h3 className="text-xl font-bold text-foreground">Cookie & Local Storage Preferences</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Modeled in strict compliance with international ePrivacy, GDPR, and LGPD data protection guidelines.
          </p>
        </div>

        {/* Global Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
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
            Reject Non-Essential
          </button>
        </div>
      </div>

      {/* Preferences List */}
      <div className="divide-y divide-border/60 py-4 space-y-4">
        {/* 1. Strictly Necessary */}
        <div className="pt-4 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1 max-w-xl">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-emerald-500" />
              <h4 className="text-sm font-semibold text-foreground">Strictly Necessary Technologies</h4>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                Always Required
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              These cookies and storage items are essential to provide services and features you request, such as secure session tokens, CSRF protection, and DDoS mitigation routing. They cannot be disabled.
            </p>
          </div>
          <div className="flex items-center">
            <div className="relative inline-flex h-6 w-11 shrink-0 cursor-not-allowed items-center rounded-full bg-emerald-600 opacity-80 transition-colors">
              <span className="translate-x-6 inline-block h-4 w-4 rounded-full bg-white transition-transform" />
            </div>
          </div>
        </div>

        {/* 2. Functional & Preferences */}
        <div className="pt-4 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1 max-w-xl">
            <div className="flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-cyan-500" />
              <h4 className="text-sm font-semibold text-foreground">Functional & Preference Storage</h4>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                Customizable
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Used to remember your choices across pages, such as playground code buffer persistence, code editor split view states, and preferred terminal installation tab (e.g. `sotlas pkg` vs `curl`).
            </p>
          </div>
          <div className="flex items-center">
            <button
              type="button"
              role="switch"
              aria-checked={prefs.functional}
              onClick={() => setPrefs((prev) => ({ ...prev, functional: !prev.functional }))}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                prefs.functional ? "bg-primary" : "bg-muted border border-border"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  prefs.functional ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        {/* 3. Performance & Diagnostics */}
        <div className="pt-4 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1 max-w-xl">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-amber-500" />
              <h4 className="text-sm font-semibold text-foreground">Performance & Diagnostic Telemetry</h4>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                Optional
              </span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Enables anonymous measurement of website load speeds, playground compiler compilation response times, and error rate telemetry. No personal identities or IP addresses are retained.
            </p>
          </div>
          <div className="flex items-center">
            <button
              type="button"
              role="switch"
              aria-checked={prefs.performance}
              onClick={() => setPrefs((prev) => ({ ...prev, performance: !prev.performance }))}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                prefs.performance ? "bg-primary" : "bg-muted border border-border"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  prefs.performance ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Footer Controls & Feedback */}
      <div className="pt-6 mt-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleSave()}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-foreground text-background text-xs font-semibold hover:opacity-90 transition-opacity shadow-sm cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>Save Preferences</span>
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground text-xs transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
        </div>

        {savedFeedback && (
          <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-3 py-1.5 rounded-xl animate-in fade-in">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>{savedFeedback}</span>
          </div>
        )}
      </div>

      {/* Cookie Inventory Breakdown */}
      <div className="mt-8 pt-6 border-t border-border/80">
        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3 font-mono">
          Detailed Storage & Cookie Inventory
        </h4>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-muted/60 text-muted-foreground border-b border-border">
              <tr>
                <th className="p-3">Identifier</th>
                <th className="p-3">Category</th>
                <th className="p-3">Storage Type</th>
                <th className="p-3">Duration</th>
                <th className="p-3">Purpose</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 text-foreground/80">
              <tr>
                <td className="p-3 font-semibold text-foreground">sotlas_cookie_preferences</td>
                <td className="p-3 text-emerald-400">Strictly Necessary</td>
                <td className="p-3">localStorage</td>
                <td className="p-3">1 Year</td>
                <td className="p-3">Stores your consent choices and privacy preferences.</td>
              </tr>
              <tr>
                <td className="p-3 font-semibold text-foreground">sotlas_playground_code</td>
                <td className="p-3 text-cyan-400">Functional</td>
                <td className="p-3">localStorage</td>
                <td className="p-3">Persistent</td>
                <td className="p-3">Saves in-progress code edits in the interactive web playground.</td>
              </tr>
              <tr>
                <td className="p-3 font-semibold text-foreground">sotlas_session_nav</td>
                <td className="p-3 text-emerald-400">Strictly Necessary</td>
                <td className="p-3">sessionStorage</td>
                <td className="p-3">Session</td>
                <td className="p-3">Maintains scroll position and documentation search history.</td>
              </tr>
              <tr>
                <td className="p-3 font-semibold text-foreground">sotlas_perf_metrics</td>
                <td className="p-3 text-amber-400">Performance</td>
                <td className="p-3">sessionStorage</td>
                <td className="p-3">Session</td>
                <td className="p-3">Anonymous WebAssembly compiler runtime benchmarking data.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
