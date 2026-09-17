/**
 * SotlasLogoBackground
 * Uses anime.js v4 for high-performance SVG animations.
 * Phase 1 – Mount assembly: navy enters first, orange with slight delay.
 * Phase 2 – Scroll settle: logo expands and fades into background as user scrolls.
 */
import { useEffect, useRef } from "react";
import { animate, utils } from "animejs";
import sotlasSvgRaw from "@/assets/sotlas-icon-vector.svg?raw";

// ── tuneable constants ────────────────────────────────────────────────────────
const SETTLE_SCROLL_PX    = 900;
const NAVY_DURATION       = 1100;
const ORANGE_DELAY        = 150;
const ORANGE_DURATION     = 1000;

const NAVY_START_X        = -120;
const NAVY_START_Y        = -80;
const NAVY_START_ROTATE   = -18;
const NAVY_START_SCALE    = 0.72;

const ORANGE_START_X      = 130;
const ORANGE_START_Y      = 90;
const ORANGE_START_ROTATE = 16;
const ORANGE_START_SCALE  = 0.72;

const SETTLED_SCALE       = 1.85;
const SETTLED_OPACITY     = 0.07;
const SETTLED_NAVY_X      = -60;
const SETTLED_NAVY_Y      = -40;
const SETTLED_ORANGE_X    = 60;
const SETTLED_ORANGE_Y    = 40;

// ─────────────────────────────────────────────────────────────────────────────
const lerpVal = (a: number, b: number, t: number) => a + (b - a) * t;

// Preprocess SVG: wrap navy-layer groups and orange-layer groups in unified wrappers
const wrapGroups = (raw: string): string => {
  const navyPattern = /(<g class="navy-layer"[\s\S]*?<\/g>\s*){1,}/g;
  const orangePattern = /(<g class="orange-layer"[\s\S]*?<\/g>\s*){1,}/g;

  // Find boundaries of navy and orange sections
  const navyMatch = raw.match(navyPattern);
  const orangeMatch = raw.match(orangePattern);

  if (!navyMatch || !orangeMatch) return raw;

  let result = raw;

  // Wrap orange section first (from the end, so indices stay valid)
  const orangeFull = orangeMatch.join("");
  result = result.replace(
    orangeFull,
    `<g class="orange-group" style="transform-box:fill-box;transform-origin:center">${orangeFull}</g>`
  );

  // Wrap navy section
  const navyFull = navyMatch.join("");
  result = result.replace(
    navyFull,
    `<g class="navy-group" style="transform-box:fill-box;transform-origin:center">${navyFull}</g>`
  );

  return result;
};

const processedSvg = wrapGroups(sotlasSvgRaw);

// ─────────────────────────────────────────────────────────────────────────────
export function SotlasLogoBackground() {
  const containerRef = useRef<HTMLDivElement>(null);
  const navyRef      = useRef<Element | null>(null);
  const orangeRef    = useRef<Element | null>(null);
  const settleRef    = useRef(0);

  const applySettle = (t: number) => {
    const navy   = navyRef.current as HTMLElement | null;
    const orange = orangeRef.current as HTMLElement | null;
    if (!navy || !orange) return;

    const scale   = lerpVal(1, SETTLED_SCALE, t);
    const opacity = lerpVal(1, SETTLED_OPACITY, t);
    const nx      = lerpVal(0, SETTLED_NAVY_X, t);
    const ny      = lerpVal(0, SETTLED_NAVY_Y, t);
    const ox      = lerpVal(0, SETTLED_ORANGE_X, t);
    const oy      = lerpVal(0, SETTLED_ORANGE_Y, t);

    navy.style.transform   = `translate(${nx}px, ${ny}px) scale(${scale})`;
    navy.style.opacity     = String(opacity);
    orange.style.transform = `translate(${ox}px, ${oy}px) scale(${scale})`;
    orange.style.opacity   = String(opacity);
  };

  // Scroll listener for settle phase
  useEffect(() => {
    const onScroll = () => {
      const t = Math.min(window.scrollY / SETTLE_SCROLL_PX, 1);
      settleRef.current = t;
      applySettle(t);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mount animation with anime.js
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const navy   = container.querySelector(".navy-group");
    const orange = container.querySelector(".orange-group");
    if (!navy || !orange) {
      console.warn("[SotlasLogoBackground] Groups not found — check SVG preprocessing.");
      return;
    }

    navyRef.current   = navy;
    orangeRef.current = orange;

    const navyEl   = navy as HTMLElement;
    const orangeEl = orange as HTMLElement;

    navyEl.style.transformBox    = "fill-box";
    navyEl.style.transformOrigin = "center";
    orangeEl.style.transformBox    = "fill-box";
    orangeEl.style.transformOrigin = "center";

    // Set initial scattered positions
    utils.set(navyEl, {
      translateX: NAVY_START_X,
      translateY: NAVY_START_Y,
      rotate:     NAVY_START_ROTATE,
      scale:      NAVY_START_SCALE,
      opacity:    0,
    });

    utils.set(orangeEl, {
      translateX: ORANGE_START_X,
      translateY: ORANGE_START_Y,
      rotate:     ORANGE_START_ROTATE,
      scale:      ORANGE_START_SCALE,
      opacity:    0,
    });

    // Navy assembles first
    animate(navyEl, {
      translateX: 0,
      translateY: 0,
      rotate:     0,
      scale:      1,
      opacity:    1,
      duration:   NAVY_DURATION,
      delay:      80,
      ease:       "out(3)",
    });

    // Orange assembles with slight delay — feels like the two ribbons meet
    animate(orangeEl, {
      translateX: 0,
      translateY: 0,
      rotate:     0,
      scale:      1,
      opacity:    1,
      duration:   ORANGE_DURATION,
      delay:      ORANGE_DELAY + 80,
      ease:       "out(3)",
    });

    // After animation completes, blend with current scroll state
    const afterId = setTimeout(() => {
      applySettle(settleRef.current);
    }, ORANGE_DURATION + ORANGE_DELAY + 300);

    return () => clearTimeout(afterId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 z-0 pointer-events-none overflow-hidden"
      style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      <div
        ref={containerRef}
        style={{
          width: "min(85vw, 85vh)",
          height: "min(85vw, 85vh)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        dangerouslySetInnerHTML={{ __html: processedSvg }}
      />
    </div>
  );
}

export default SotlasLogoBackground;
