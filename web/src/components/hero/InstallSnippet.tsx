import { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";

interface InstallOption {
  id: "unix" | "windows" | "pkg";
  label: string;
  command: string;
}

const installOptions: InstallOption[] = [
  {
    id: "unix",
    label: "Linux / macOS",
    command: "curl -proto '=https' --tlsv1.2 -sSf https://sotlas.org/install.sh | sh",
  },
  {
    id: "windows",
    label: "Windows (PowerShell)",
    command: "irm https://sotlas.org/install.ps1 | iex",
  },
  {
    id: "pkg",
    label: "Sotlas Toolchain",
    command: "sotlasup toolchain install stable",
  },
];

export function InstallSnippet() {
  const [selectedId, setSelectedId] = useState<"unix" | "windows" | "pkg">("unix");
  const [copied, setCopied] = useState(false);

  const currentOption = installOptions.find((o) => o.id === selectedId) || installOptions[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentOption.command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Falha ao copiar:", err);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto my-6">
      <div className="rounded-2xl border border-border bg-card/80 dark:bg-card/60 backdrop-blur-sm shadow-md overflow-hidden transition-all">
        {/* Top tabs */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/40 text-xs font-mono">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <Terminal className="w-3.5 h-3.5 text-primary" />
            <span className="font-semibold text-foreground/80 hidden sm:inline">Official Install:</span>
            <div className="flex items-center gap-1">
              {installOptions.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSelectedId(opt.id)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    selectedId === opt.id
                      ? "bg-background text-foreground shadow-xs border border-border font-semibold"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <span className="text-[11px] text-muted-foreground font-mono hidden md:inline">
            v0.5.1 Official
          </span>
        </div>

        {/* Command bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-muted/40 text-foreground font-mono text-xs sm:text-sm">
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-none pr-3">
            <span className="text-primary font-bold select-none">$</span>
            <code className="whitespace-nowrap text-foreground font-medium">{currentOption.command}</code>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card hover:bg-secondary text-foreground border border-border transition-all shrink-0 text-xs font-sans font-medium shadow-2xs cursor-pointer"
            title="Copy command"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-500 font-semibold">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default InstallSnippet;
