import { motion } from "framer-motion";
import ChangelogBadge from "./ChangelogBadge";

type BadgeVariant = "fixes" | "improvements" | "features";

interface ChangelogSection {
  title: string;
  items: string[];
  code?: {
    lines: string[];
  };
}

interface ChangelogEntryProps {
  date: string;
  badges: { variant: BadgeVariant; label: string }[];
  sections: ChangelogSection[];
  index: number;
}

const ChangelogEntry = ({ date, badges, sections, index }: ChangelogEntryProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
      className="flex flex-col md:flex-row gap-6 md:gap-12"
    >
      {/* Left Side - Date & Badges */}
      <div className="md:w-48 md:sticky md:top-24 md:self-start flex-shrink-0">
        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-muted-foreground">
            {date}
          </span>
          <div className="flex flex-row md:flex-col gap-2 flex-wrap">
            {badges.map((badge, i) => (
              <ChangelogBadge key={i} variant={badge.variant}>
                {badge.label}
              </ChangelogBadge>
            ))}
          </div>
        </div>
      </div>

      {/* Right Side - Content */}
      <div className="flex-1 pb-12 border-b border-border last:border-b-0">
        <div className="space-y-6">
          {sections.map((section, sectionIndex) => (
            <div key={sectionIndex} className="space-y-3">
              <h3 className="text-lg font-semibold text-foreground">
                {section.title}
              </h3>
              <ul className="space-y-2">
                {section.items.map((item, itemIndex) => (
                  <li
                    key={itemIndex}
                    className="flex items-start gap-2 text-muted-foreground text-sm leading-relaxed"
                  >
                    <span className="text-primary mt-1.5 w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              {section.code && (
                <div className="mt-4 rounded-lg bg-secondary/50 border border-border overflow-hidden">
                  <div className="p-4 font-mono text-sm">
                    {section.code.lines.map((line, lineIndex) => (
                      <div key={lineIndex} className="text-muted-foreground">
                        <span className="text-primary/80">{line}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

export default ChangelogEntry;
