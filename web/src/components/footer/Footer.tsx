import { Link } from "react-router-dom";

const footerSections = [
  {
    title: "Language",
    links: [
      { label: "Overview", href: "/docs/overview" },
      { label: "Syntax & Declarations", href: "/docs/syntax" },
      { label: "Types & Bounded Types", href: "/docs/types" },
      { label: "SRG Memory Graph", href: "/docs/memory" },
      { label: "Topology Pointers", href: "/docs/pointers" },
      { label: "C & C++ Interoperability", href: "/docs/interoperability" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Documentation", href: "/docs/overview" },
      { label: "VS Code Setup & Tutorial", href: "/docs/vscode-tutorial" },
      { label: "API Reference", href: "/api/search-packages" },
      { label: "Installation", href: "/docs/installation" },
      { label: "Changelog", href: "/changelog" },
      { label: "Playground", href: "/playground" },
      { label: "Compiler Pipeline", href: "/docs/compiler" },
    ],
  },
  {
    title: "Community",
    links: [
      { label: "Community", href: "/community" },
      { label: "GitHub Repository", href: "https://github.com/Sotlas/sotlas", external: true },
      { label: "GitHub Issues", href: "https://github.com/Sotlas/sotlas/issues", external: true },
      { label: "Discussions", href: "https://github.com/Sotlas/sotlas/discussions", external: true },
      { label: "Contributing", href: "/docs/community" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Apache 2.0 License", href: "https://github.com/Sotlas/sotlas/blob/main/LICENSE", external: true },
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Cookies", href: "/privacy#cookies" },
    ],
  },
];

const Footer = () => {
  return (
    <footer className="border-t border-border/80 bg-[#05070d]">
      {/* Main Footer Grid */}
      <div className="max-w-7xl mx-auto px-4 md:px-8 pt-12 pb-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-10">
          {footerSections.map((section) => (
            <div key={section.title}>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">
                {section.title}
              </h4>
              <ul className="space-y-2.5">
                {section.links.map((link) => {
                  const isExternal = "external" in link && link.external;
                  return (
                    <li key={link.label}>
                      {isExternal ? (
                        <a
                          href={link.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-slate-500 hover:text-slate-200 transition-colors"
                        >
                          {link.label}
                        </a>
                      ) : (
                        <Link
                          to={link.href}
                          className="text-sm text-slate-500 hover:text-slate-200 transition-colors"
                        >
                          {link.label}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 md:px-8 py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Left: Logo + Copyright */}
          <div className="flex items-center gap-3">
            <img
              src="/icone-sotlas.svg"
              alt="Sotlas"
              className="w-6 h-6 opacity-60"
            />
            <span className="text-xs text-slate-500">
              © 2026 <strong className="font-semibold text-slate-400">Hiago Pinho</strong>. Apache 2.0 License.
            </span>
          </div>

          {/* Right: Social Links */}
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/Sotlas/sotlas"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-slate-200 transition-colors"
              aria-label="GitHub"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </a>
            <span className="text-[11px] text-slate-600 font-mono">
              Sotlas v0.5.1
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;