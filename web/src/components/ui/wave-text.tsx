import { motion } from "framer-motion";
import { useIsMobile } from "@/hooks/use-mobile";

interface WaveTextProps {
  text: string;
  className?: string;
  as?: React.ElementType;
  staggerDelay?: number;
  yOffset?: number;
  duration?: number;
}

const WaveText = ({
  text,
  className = "",
  as: Component = "span",
  staggerDelay = 0.03,
  yOffset = 20,
  duration = 0.4,
}: WaveTextProps) => {
  const isMobile = useIsMobile();
  
  const words = text.split(" ");

  const containerVariants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: isMobile ? staggerDelay * 2 : staggerDelay,
      },
    },
  };

  const itemVariants = {
    hidden: {
      y: yOffset,
      opacity: 0,
    },
    visible: {
      y: 0,
      opacity: 1,
      transition: {
        duration: duration,
        ease: [0.25, 0.1, 0.25, 1] as const,
      },
    },
  };

  return (
    <motion.span
      className={className}
      variants={containerVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-100px" }}
      aria-label={text}
    >
      {words.map((word, wordIdx) => (
        <span
          key={wordIdx}
          style={{ display: "inline-block", whiteSpace: "nowrap" }}
        >
          {isMobile ? (
            <motion.span
              variants={itemVariants}
              style={{ display: "inline-block" }}
              aria-hidden="true"
            >
              {word}
            </motion.span>
          ) : (
            word.split("").map((char, charIdx) => (
              <motion.span
                key={charIdx}
                variants={itemVariants}
                style={{ display: "inline-block" }}
                aria-hidden="true"
              >
                {char}
              </motion.span>
            ))
          )}
          {wordIdx < words.length - 1 && "\u00A0"}
        </span>
      ))}
    </motion.span>
  );
};

export default WaveText;
