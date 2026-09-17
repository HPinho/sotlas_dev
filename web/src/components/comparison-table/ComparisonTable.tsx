import { motion } from "framer-motion";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import WaveText from "@/components/ui/wave-text";

type CellStatus = "yes" | "no" | "partial";

interface ComparisonRow {
  feature: string;
  sotlas: { status: CellStatus; detail: string };
  c: { status: CellStatus; detail: string };
  cpp: { status: CellStatus; detail: string };
  objc: { status: CellStatus; detail: string };
}

const rows: ComparisonRow[] = [
  {
    feature: "Safety by Default",
    sotlas: { status: "yes", detail: "Yes" },
    c: { status: "no", detail: "No" },
    cpp: { status: "no", detail: "No" },
    objc: { status: "no", detail: "No" },
  },
  {
    feature: "Privilege vs Memory Separation",
    sotlas: { status: "yes", detail: "@system vs unsafe" },
    c: { status: "no", detail: "Mixed" },
    cpp: { status: "no", detail: "Mixed" },
    objc: { status: "no", detail: "Mixed" },
  },
  {
    feature: "Value Semantics (Zero-Cost)",
    sotlas: { status: "yes", detail: "Value struct" },
    c: { status: "yes", detail: "Basic struct" },
    cpp: { status: "partial", detail: "Manual copy/move" },
    objc: { status: "no", detail: "Heap objects mostly" },
  },
  {
    feature: "Reference Counting (ARC)",
    sotlas: { status: "yes", detail: "Native & predictable" },
    c: { status: "no", detail: "Manual" },
    cpp: { status: "partial", detail: "Heavy shared_ptr" },
    objc: { status: "partial", detail: "ARC + dynamic runtime" },
  },
  {
    feature: "Module System",
    sotlas: { status: "yes", detail: "module & import" },
    c: { status: "no", detail: "Textual #include" },
    cpp: { status: "partial", detail: "Complex modules" },
    objc: { status: "no", detail: "#include / #import" },
  },
  {
    feature: "Contracts and Protocols",
    sotlas: { status: "yes", detail: "spec / adopts" },
    c: { status: "no", detail: "Nonexistent" },
    cpp: { status: "partial", detail: "Multiple inheritance / Concepts" },
    objc: { status: "partial", detail: "Dynamic protocols" },
  },
  {
    feature: "Typed Error Handling",
    sotlas: { status: "yes", detail: "Option<T> / Result<T, E>" },
    c: { status: "no", detail: "Magic error ints" },
    cpp: { status: "partial", detail: "Exceptions (banned in kernel)" },
    objc: { status: "partial", detail: "NSError / nil checks" },
  },
  {
    feature: "Bare-Metal Target",
    sotlas: { status: "yes", detail: "1st-class citizen" },
    c: { status: "yes", detail: "Native" },
    cpp: { status: "partial", detail: "Hard without runtime" },
    objc: { status: "no", detail: "Incompatible without runtime" },
  },
  {
    feature: "SSA Intermediate Representation",
    sotlas: { status: "yes", detail: "SIR (Sotlas IR)" },
    c: { status: "no", detail: "None" },
    cpp: { status: "no", detail: "None" },
    objc: { status: "no", detail: "None" },
  },
  {
    feature: "Stable Bidirectional C ABI",
    sotlas: { status: "yes", detail: "100% guaranteed" },
    c: { status: "yes", detail: "Native" },
    cpp: { status: "partial", detail: "Partial extern \"C\"" },
    objc: { status: "partial", detail: "Fragile outside Apple" },
  },
];

function StatusIcon({ status }: { status: CellStatus }) {
  switch (status) {
    case "yes":
      return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    case "no":
      return <XCircle className="w-4 h-4 text-red-400" />;
    case "partial":
      return <AlertTriangle className="w-4 h-4 text-amber-500" />;
  }
}

const langHeaders = [
  { name: "Sotlas", color: "text-orange-600 dark:text-orange-400", highlight: true },
  { name: "C11", color: "text-zinc-600 dark:text-zinc-400", highlight: false },
  { name: "C++20", color: "text-blue-600 dark:text-blue-400", highlight: false },
  { name: "Obj-C", color: "text-violet-600 dark:text-violet-400", highlight: false },
];

export function ComparisonTable() {
  return (
    <section className="px-4 md:px-8 py-16 md:py-24 relative overflow-hidden">
      <div className="absolute top-1/4 right-0 w-96 h-96 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.05)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Section Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-mono mb-3">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Comparison Matrix</span>
          </div>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground tracking-tight mb-4">
            <WaveText text="Detailed Technical Comparison" />
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto leading-relaxed">
            Sotlas versus legacy systems languages across every critical engineering dimension.
          </p>
        </div>

        {/* Desktop Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.1 }}
          transition={{ duration: 0.6 }}
          className="hidden md:block rounded-3xl border border-border bg-card overflow-hidden shadow-lg"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-6 py-4 font-semibold text-foreground text-xs uppercase tracking-wider w-[30%]">
                    Feature / Challenge
                  </th>
                  {langHeaders.map((lang) => (
                    <th
                      key={lang.name}
                      className={`text-center px-4 py-4 font-bold text-sm ${lang.color} ${lang.highlight ? "bg-orange-500/5" : ""}`}
                    >
                      {lang.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr
                    key={row.feature}
                    className={`border-b border-border/50 transition-colors hover:bg-muted/20 ${idx % 2 === 0 ? "" : "bg-muted/10"}`}
                  >
                    <td className="px-6 py-3.5 font-medium text-foreground/90 text-[13px]">
                      {row.feature}
                    </td>
                    {(["sotlas", "c", "cpp", "objc"] as const).map((lang) => {
                      const cell = row[lang];
                      const isHighlight = lang === "sotlas";
                      return (
                        <td
                          key={lang}
                          className={`text-center px-4 py-3.5 ${isHighlight ? "bg-orange-500/5" : ""}`}
                        >
                          <div className="flex flex-col items-center gap-1">
                            <StatusIcon status={cell.status} />
                            <span className="text-[11px] text-muted-foreground font-mono leading-tight">
                              {cell.detail}
                            </span>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Mobile Cards */}
        <div className="md:hidden space-y-4">
          {rows.map((row, idx) => (
            <motion.div
              key={row.feature}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 0.3, delay: idx * 0.04 }}
              className="rounded-2xl border border-border bg-card p-4 shadow-xs"
            >
              <h4 className="text-sm font-semibold text-foreground mb-3">{row.feature}</h4>
              <div className="grid grid-cols-2 gap-2">
                {(["sotlas", "c", "cpp", "objc"] as const).map((lang, langIdx) => {
                  const cell = row[lang];
                  const header = langHeaders[langIdx];
                  return (
                    <div
                      key={lang}
                      className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${lang === "sotlas" ? "border-orange-500/30 bg-orange-500/5" : "border-border/50 bg-muted/30"}`}
                    >
                      <StatusIcon status={cell.status} />
                      <div>
                        <span className={`text-[10px] font-bold ${header.color} block`}>{header.name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">{cell.detail}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default ComparisonTable;
