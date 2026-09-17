import { useState, useEffect } from "react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Seo } from "@/components/Seo";
import {
  ShieldCheck,
  Lock,
  FileText,
  UserCheck,
  Eye,
  Database,
  Globe,
  HelpCircle,
  Building2,
  CheckCircle2,
  Copy,
  Check,
  Mail,
  Download,
  ExternalLink,
} from "lucide-react";
import WaveText from "@/components/ui/wave-text";
import { CookiePreferencesManager } from "@/components/cookie-manager/CookiePreferencesManager";

export function PrivacyPolicy() {
  const [copiedEmail, setCopiedEmail] = useState(false);

  const handleCopyEmail = () => {
    navigator.clipboard.writeText("privacy@tastetrack.com.br");
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 3000);
  };

  const handleDownloadSummary = () => {
    const text = `TasteTrack Systems LTDA — Privacy Policy & Cookie Charter
CNPJ/MF: 67.135.093/0001-32
Headquarters: Quadra Ap, 02, Santa Maria, Teresina - PI, Brazil, CEP: 64012-348
DPO Contact: privacy@tastetrack.com.br
Effective Date: September 2026 (Version 1.4)

1. DATA CONTROLLER COMMITMENT
TasteTrack Systems LTDA guarantees compliance with the Brazilian General Data Protection Law (LGPD - Law nº 13.709/2018), GDPR, and global privacy standards.

2. ZERO THIRD-PARTY TRACKING GUARANTEE
We do not sell, rent, or monetize personal data. We do not use third-party behavioral advertising cookies or cross-site tracking pixels.

3. COOKIE TAXONOMY (APPLE LEGAL STANDARD)
- Strictly Necessary: Required for session continuity, DDoS mitigation, and CSRF defense.
- Functional: Preserves developer theme choices, layout split views, and playground buffers.
- Performance: Anonymous compile latency telemetry with zero personal identifiers.

For formal inquiries, contact: privacy@tastetrack.com.br`;

    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "TasteTrack_Privacy_Charter_2026.txt";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (window.location.hash) {
      const rawId = window.location.hash.replace("#", "");
      const aliasMap: Record<string, string> = {
        preambulo: "controller",
        definicoes: "definitions",
        direitos: "rights",
        coleta: "collection",
        finalidade: "purposes",
        compartilhamento: "sharing",
        seguranca: "security",
        retencao: "retention",
        contato: "contact",
      };
      const id = aliasMap[rawId] || rawId;
      const elem = document.getElementById(id);
      if (elem) {
        setTimeout(() => {
          elem.scrollIntoView({ behavior: "smooth" });
        }, 150);
      }
    }
  }, []);

  const sections = [
    { id: "controller", title: "1. Data Controller Identification" },
    { id: "definitions", title: "2. Personal Data Definitions" },
    { id: "rights", title: "3. Privacy Rights (LGPD / GDPR)" },
    { id: "collection", title: "4. Data We Collect" },
    { id: "purposes", title: "5. Purposes & Legal Bases" },
    { id: "sharing", title: "6. Data Sharing" },
    { id: "security", title: "7. Information Security" },
    { id: "cookies", title: "8. Cookies & Session Technologies" },
    { id: "retention", title: "9. Data Retention & Deletion" },
    { id: "contact", title: "10. Contact & DPO Channel" },
  ];

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      <Seo
        title="Privacy Policy — TasteTrack Systems & Sotlas"
        description="Privacy terms and data protection policies of TasteTrack Systems LTDA for the Sotlas ecosystem, in compliance with LGPD and global standards."
        path="/privacy"
      />
      <Navbar />

      <main className="pt-32 md:pt-40 pb-20 px-4 md:px-8">
        <div className="max-w-5xl mx-auto">
          {/* Header Banner */}
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-emerald-950/40 border border-emerald-800/60 text-xs font-mono text-emerald-400 mb-4">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Legal Compliance & Data Protection</span>
            </div>
            <h1 className="text-3xl md:text-5xl font-bold text-foreground tracking-tight mb-4">
              <WaveText text="TasteTrack Privacy Policy" />
            </h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto leading-relaxed">
              At TasteTrack Systems LTDA, privacy is a fundamental human right. Learn how we safeguard your information across the Sotlas language ecosystem.
            </p>
            <p className="text-xs font-mono text-zinc-500 mt-4">
              Effective Date: September 2026 · Version 1.4
            </p>
          </div>

          {/* Grid Layout: Table of Contents + Content */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Quick Navigation Sidebar */}
            <aside className="lg:col-span-1 hidden lg:block">
              <div className="sticky top-28 p-5 rounded-2xl bg-card border border-border text-xs space-y-2 shadow-xs">
                <p className="font-bold text-foreground uppercase tracking-wider mb-3 font-mono text-[11px] text-muted-foreground">
                  Document Navigation
                </p>
                {sections.map((sec) => (
                  <a
                    key={sec.id}
                    href={`#${sec.id}`}
                    className="block text-muted-foreground hover:text-foreground transition-colors py-1 pl-2 border-l border-border hover:border-orange-500"
                  >
                    {sec.title}
                  </a>
                ))}
              </div>
            </aside>

            {/* Document Content */}
            <div className="lg:col-span-3 space-y-10 text-sm leading-relaxed text-foreground/90">
              {/* 1. Controller Identification */}
              <section id="controller" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Building2 className="w-5 h-5 text-orange-500" />
                  <h2>1. Identification of the Data Controller</h2>
                </div>
                <div className="p-4 rounded-xl bg-muted/50 border border-border font-mono text-xs text-foreground mb-4 leading-relaxed">
                  <strong>TasteTrack Systems LTDA</strong>, a corporate entity organized and existing under the laws of Brazil, registered under CNPJ/MF nº <strong>67.135.093/0001-32</strong>, headquartered at <strong>Quadra Ap, 02, Santa Maria, Teresina - PI, CEP: 64012-348</strong> (hereinafter referred to as &quot;TasteTrack Systems&quot;, &quot;we&quot;, or &quot;us&quot;), maintains a steadfast commitment to protecting your privacy and personal data, in strict compliance with the <strong>Brazilian General Data Protection Law (LGPD — Law nº 13.709/2018)</strong> and international standards.
                </div>
                <p>
                  This Privacy Policy transparently governs how personal data is collected, used, processed, stored, and protected when you interact with the Sotlas language portal, official repositories, compilation tools, documentation, and technical support channels.
                </p>
              </section>

              {/* 2. Definitions */}
              <section id="definitions" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <FileText className="w-5 h-5 text-blue-400" />
                  <h2>2. What Constitutes Personal Data</h2>
                </div>
                <p className="mb-3">
                  At TasteTrack, we enforce strict transparency: personal data constitutes any information relating to an identified or identifiable natural person. Data that has been irreversibly anonymized, such that individual identity cannot be ascertained, is not classified as personal data.
                </p>
                <p>
                  We believe that privacy begins with <strong>data minimization</strong>: we collect only what is strictly necessary to deliver accurate documentation, performant developer tooling, and robust infrastructure security.
                </p>
              </section>

              {/* 3. Your Rights */}
              <section id="rights" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <UserCheck className="w-5 h-5 text-emerald-400" />
                  <h2>3. Your Privacy Rights</h2>
                </div>
                <p className="mb-4">
                  In compliance with applicable data protection legislation, TasteTrack guarantees your fundamental rights as a data subject:
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {[
                    "Confirmation of the existence of data processing",
                    "Right to access processed personal data",
                    "Correction of incomplete, inaccurate, or outdated data",
                    "Anonymization, blocking, or elimination of unnecessary data",
                    "Data portability to another service provider",
                    "Information regarding public and private entities with whom data is shared",
                    "Revocation of consent at any time",
                    "Right to object to processing grounded in legal bases",
                  ].map((right, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                      <span>{right}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* 4. Data Collected */}
              <section id="collection" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Database className="w-5 h-5 text-cyan-400" />
                  <h2>4. Personal Data We Collect</h2>
                </div>
                <p className="mb-3">
                  Depending on how you interact with the Sotlas ecosystem, we may process:
                </p>
                <ul className="list-disc pl-5 space-y-2 text-zinc-300 mb-4">
                  <li>
                    <strong>Technical Navigation Data:</strong> Truncated IP addresses, HTTP request logs (server logs for DDoS mitigation, load balancing, and uptime stability), browser type, and operating system platform.
                  </li>
                  <li>
                    <strong>Contribution & Community Data:</strong> Public developer identifiers (GitHub/GitLab handle), email addresses linked to cryptographically signed commits or pull requests on official specifications.
                  </li>
                  <li>
                    <strong>Support & Feedback Data:</strong> Voluntary communications, questions, bug reports, and telemetry traces submitted through technical support channels.
                  </li>
                </ul>
                <div className="p-3.5 rounded-xl bg-orange-950/20 border border-orange-800/40 text-xs text-orange-300">
                  <strong>We never collect sensitive personal data</strong> (such as racial origin, religious beliefs, political opinions, genetic data, or biometric data) under any operational scenario of this website.
                </div>
              </section>

              {/* 5. Purpose & Legal Basis */}
              <section id="purposes" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Eye className="w-5 h-5 text-purple-400" />
                  <h2>5. Purposes & Legal Bases for Processing</h2>
                </div>
                <p className="mb-3">
                  TasteTrack processes personal data exclusively under legitimate legal grounds recognized by privacy frameworks:
                </p>
                <ul className="space-y-3">
                  <li className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800">
                    <strong className="text-foreground">Legitimate Interests:</strong> Ensuring platform stability, defending against cyberattacks, mitigating infrastructure abuse, and improving language documentation.
                  </li>
                  <li className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800">
                    <strong className="text-foreground">Legal & Regulatory Compliance:</strong> Mandatory retention of connection records pursuant to statutory telecommunications and internet framework laws.
                  </li>
                  <li className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800">
                    <strong className="text-foreground">Explicit Consent:</strong> Where explicitly provided by you to receive technical updates, releases, or developer newsletters.
                  </li>
                </ul>
              </section>

              {/* 6. Data Sharing */}
              <section id="sharing" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Globe className="w-5 h-5 text-amber-400" />
                  <h2>6. Data Sharing & Third Parties</h2>
                </div>
                <p className="mb-3 font-semibold text-foreground">
                  TasteTrack Systems LTDA DOES NOT sell, rent, or trade personal data with data brokers or behavioral advertising networks.
                </p>
                <p>
                  Data sharing is strictly confined to technical infrastructure vendors bound by robust confidentiality obligations (e.g. secure cloud hosting and content delivery networks/CDNs) and to competent authorities when compelled by lawful judicial process.
                </p>
              </section>

              {/* 7. Information Security */}
              <section id="security" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Lock className="w-5 h-5 text-emerald-400" />
                  <h2>7. Information Protection & Security</h2>
                </div>
                <p className="mb-3">
                  We deploy rigorous administrative and technical security safeguards aligned with industry best practices:
                </p>
                <ul className="list-disc pl-5 space-y-1.5 text-zinc-300">
                  <li>End-to-end encryption via TLS 1.3 / HTTPS across all client-server communications.</li>
                  <li>Strict access controls enforced under the principle of least privilege.</li>
                  <li>Automated monitoring and mitigation against Distributed Denial of Service (DDoS) attacks.</li>
                  <li>Isolated development, staging, and production environments.</li>
                </ul>
              </section>

              {/* 8. Cookies */}
              <section id="cookies" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs space-y-6">
                <div>
                  <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                    <ShieldCheck className="w-5 h-5 text-cyan-400" />
                    <h2>8. Cookies & Local Storage Technologies</h2>
                  </div>
                  <p className="mb-3 leading-relaxed">
                    Like most modern web platforms and developer tooling portals, TasteTrack Systems LTDA utilizes cookies and equivalent local storage technologies (including HTML5 localStorage and sessionStorage). In accordance with international privacy frameworks (ePrivacy Directive, GDPR, and LGPD), we categorize these technologies into distinct operational tiers:
                  </p>
                  <ul className="list-disc pl-5 space-y-2 text-zinc-300 text-xs md:text-sm">
                    <li>
                      <strong>Strictly Necessary Technologies:</strong> Indispensable for establishing secure TLS sessions, defending against Distributed Denial of Service (DDoS) traffic, maintaining CSRF protection, and preserving core navigation state. These cannot be disabled.
                    </li>
                    <li>
                      <strong>Functional & Developer Preferences:</strong> Retain client-side state across sessions, such as code written inside the interactive Web Playground, split-screen code view configurations, and active documentation search filters.
                    </li>
                    <li>
                      <strong>Performance & Diagnostics:</strong> Gather completely aggregated, non-identifiable telemetry regarding compiler compilation latencies and page load benchmarks to guide infrastructure scaling.
                    </li>
                    <li>
                      <strong>Zero Third-Party Advertising:</strong> TasteTrack maintains an absolute prohibition against third-party marketing cookies, cross-site trackers, behavioral ad pixels, and data brokers.
                    </li>
                  </ul>
                </div>

                {/* Embedded Interactive Cookie Preferences Manager */}
                <CookiePreferencesManager />
              </section>

              {/* 9. Retention */}
              <section id="retention" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs">
                <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                  <Database className="w-5 h-5 text-blue-400" />
                  <h2>9. Data Retention & Deletion</h2>
                </div>
                <p>
                  Personal data is retained only for the duration strictly necessary to accomplish the purposes for which it was gathered, or to comply with statutory retention mandates. Upon expiration of the applicable retention period, data is securely erased or irreversibly anonymized.
                </p>
              </section>

              {/* 10. Contact / DPO */}
              <section id="contact" className="p-6 md:p-8 rounded-3xl bg-card border border-border shadow-xs space-y-6">
                <div>
                  <div className="flex items-center gap-3 mb-4 text-foreground font-bold text-lg">
                    <HelpCircle className="w-5 h-5 text-orange-400" />
                    <h2>10. Data Subject Inquiries & DPO Contact</h2>
                  </div>
                  <p className="mb-4">
                    To exercise your data protection rights, request information, or submit questions regarding this policy, please contact our Data Protection Office directly:
                  </p>
                  <div className="p-5 rounded-2xl bg-zinc-950 border border-zinc-800 space-y-2 font-mono text-xs">
                    <p className="text-foreground font-bold">TasteTrack Systems LTDA — Privacy & Data Protection</p>
                    <p className="text-zinc-400">CNPJ/MF: 67.135.093/0001-32</p>
                    <p className="text-zinc-400">Address: Quadra Ap, 02, Santa Maria, Teresina - PI, Brazil, CEP: 64012-348</p>
                    <p className="text-zinc-400">
                      Privacy & DPO Inquiries: <span className="text-emerald-400">privacy@tastetrack.com.br</span>
                    </p>
                  </div>
                </div>

                {/* Functional Interactive Legal Buttons */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleCopyEmail}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-foreground text-background text-xs font-semibold hover:opacity-90 transition-opacity shadow-sm cursor-pointer"
                  >
                    {copiedEmail ? (
                      <>
                        <Check className="w-4 h-4 text-emerald-600" />
                        <span>Copied to Clipboard!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        <span>Copy DPO Email</span>
                      </>
                    )}
                  </button>

                  <a
                    href="mailto:privacy@tastetrack.com.br?subject=Sotlas%20Privacy%20Inquiry"
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-foreground text-xs font-medium transition-colors"
                  >
                    <Mail className="w-4 h-4 text-primary" />
                    <span>Open Email Client</span>
                  </a>

                  <button
                    type="button"
                    onClick={handleDownloadSummary}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground hover:text-foreground text-xs font-medium transition-colors cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Legal Charter (TXT)</span>
                  </button>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default PrivacyPolicy;
