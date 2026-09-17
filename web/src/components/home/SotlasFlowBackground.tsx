/**
 * SotlasFlowBackground — Ribbon Draw-on-Scroll
 *
 * Two long, smooth ribbon paths (navy + orange) that traverse the entire page
 * height. As the user scrolls, each ribbon progressively "draws" itself using
 * stroke-dashoffset driven by scroll position. The ribbons exist behind all
 * content as a subtle background texture.
 *
 * ─ Navy ribbon: meanders left-to-right, starting upper-left
 * ─ Orange ribbon: counter-meanders right-to-left, starting upper-right
 *
 * Both ribbons have parallax: they scroll slightly slower than the page content,
 * giving depth. anime.js v4 handles the initial mount fade-in.
 */
import { useEffect, useRef, useCallback } from "react";
import { animate } from "animejs";

// ── Path definitions ─────────────────────────────────────────────────────────
// These are two smooth cubic Bézier curves that span the full page height.
// Coordinates are in a 1440×8700 viewBox (page width × approximate total height).
// Each curve hits approximately 7 "waypoints" — one near the top of each section.

const NAVY_RIBBON =
  "M -80,120 " +                      // start off-screen left, near hero top
  "C 280,60 520,400 720,500 " +        // curve through hero center
  "S 1100,350 1460,700 " +             // exit right near hero bottom
  "C 1200,850 800,900 600,1050 " +     // re-enter: Why Sotlas section
  "S 100,1200 -40,1500 " +             // sweep left through pillars
  "C 80,1700 500,1800 750,1950 " +     // Critical Layers section
  "S 1200,2100 1500,2400 " +           // exit right
  "C 1300,2700 900,2900 700,3200 " +   // Code Stories section
  "S 200,3500 -60,3800 " +             // sweep far left
  "C 100,4100 600,4300 800,4600 " +    // Comparison section
  "S 1300,4900 1520,5200 " +           // exit right
  "C 1400,5500 900,5700 650,6000 " +   // Manifesto section
  "S 100,6300 -80,6700 " +             // sweep left
  "C 50,7000 500,7200 750,7500 " +     // Open Source section
  "S 1300,7800 1540,8200";             // exit right, end of page

const ORANGE_RIBBON =
  "M 1520,200 " +                      // start off-screen right, hero
  "C 1200,100 900,500 720,600 " +      // curve through hero center
  "S 300,450 -40,800 " +               // exit left near hero bottom
  "C -20,950 400,1000 650,1150 " +     // Why Sotlas section
  "S 1200,1300 1520,1600 " +           // sweep right
  "C 1400,1800 1000,1900 750,2050 " +  // Critical Layers section
  "S 200,2200 -60,2500 " +             // exit left
  "C 50,2800 500,2950 750,3100 " +     // Code Stories section
  "S 1300,3400 1540,3700 " +           // exit right
  "C 1420,4000 900,4200 700,4500 " +   // Comparison section
  "S 200,4800 -80,5100 " +             // sweep left
  "C 50,5400 600,5600 800,5800 " +     // Manifesto section
  "S 1400,6100 1540,6400 " +           // exit right
  "C 1380,6700 800,6900 600,7200 " +   // Open Source section
  "S 100,7500 -60,7900 " +             // sweep left, end
  "C 80,8100 400,8400 720,8700";       // final terminus

// ── Tuneable constants ───────────────────────────────────────────────────────
const RIBBON_STROKE_WIDTH  = 22;        // px — thick enough to look like a ribbon
const NAVY_COLOR           = "#101241"; // from the Sotlas palette
const ORANGE_COLOR         = "#ea580c"; // from the Sotlas palette
const NAVY_OPACITY         = 0.22;      // subtle but visible
const ORANGE_OPACITY       = 0.18;
const PARALLAX_FACTOR      = 0.15;      // how much slower ribbons scroll vs content

// ─────────────────────────────────────────────────────────────────────────────
export function SotlasFlowBackground() {
  const svgRef     = useRef<SVGSVGElement>(null);
  const navyRef    = useRef<SVGPathElement>(null);
  const orangeRef  = useRef<SVGPathElement>(null);
  const scrollRef  = useRef(0);
  const rafRef     = useRef(0);
  const navyLen    = useRef(0);
  const orangeLen  = useRef(0);

  // ── Measure path lengths + set up dasharray on mount ──────────────────────
  useEffect(() => {
    const navy   = navyRef.current;
    const orange = orangeRef.current;
    if (!navy || !orange) return;

    // Get the real computed length of each path
    navyLen.current   = navy.getTotalLength();
    orangeLen.current = orange.getTotalLength();

    // Start fully hidden (dashoffset = full length = invisible)
    navy.style.strokeDasharray    = String(navyLen.current);
    navy.style.strokeDashoffset   = String(navyLen.current);
    orange.style.strokeDasharray  = String(orangeLen.current);
    orange.style.strokeDashoffset = String(orangeLen.current);

    // Subtle fade-in of the SVG container via anime.js
    if (svgRef.current) {
      animate(svgRef.current, {
        opacity: [0, 1],
        duration: 1200,
        delay: 200,
        ease: "out(3)",
      });
    }
  }, []);

  // ── Scroll-driven drawing + parallax ──────────────────────────────────────
  const tick = useCallback(() => {
    rafRef.current = requestAnimationFrame(tick);

    const sy     = scrollRef.current;
    const svg    = svgRef.current;
    const navy   = navyRef.current;
    const orange = orangeRef.current;
    if (!svg || !navy || !orange) return;

    // Total scrollable distance
    const docH   = document.documentElement.scrollHeight - window.innerHeight;
    // Progress: 0 at top → 1 at bottom of page
    const progress = docH > 0 ? Math.min(1, sy / docH) : 0;

    // Draw: strokeDashoffset goes from full length → 0 as progress goes 0 → 1
    // Navy draws slightly ahead, orange slightly behind (stagger feel)
    const navyDraw   = navyLen.current   * (1 - Math.min(1, progress * 1.15));
    const orangeDraw = orangeLen.current * (1 - Math.min(1, progress * 1.08));

    navy.style.strokeDashoffset   = String(navyDraw);
    orange.style.strokeDashoffset = String(orangeDraw);

    // Parallax: the whole SVG translates up slightly slower than scroll
    const parallaxY = -sy * PARALLAX_FACTOR;
    svg.style.transform = `translateY(${parallaxY}px)`;
  }, []);

  useEffect(() => {
    const onScroll = () => { scrollRef.current = window.scrollY; };
    window.addEventListener("scroll", onScroll, { passive: true });
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("scroll", onScroll);
    };
  }, [tick]);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 overflow-hidden"
      style={{ zIndex: 0 }}
    >
      <svg
        ref={svgRef}
        viewBox="0 0 1440 8700"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        style={{ opacity: 0, willChange: "transform" }}
      >
        <defs>
          {/* Glow filters for a soft neon feel */}
          <filter id="navy-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="18" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="orange-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="18" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Navy ribbon — meanders left→right→left across the page */}
        <path
          ref={navyRef}
          d={NAVY_RIBBON}
          fill="none"
          stroke={NAVY_COLOR}
          strokeWidth={RIBBON_STROKE_WIDTH}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={NAVY_OPACITY}
          filter="url(#navy-glow)"
        />

        {/* Orange ribbon — counter-meanders right→left→right */}
        <path
          ref={orangeRef}
          d={ORANGE_RIBBON}
          fill="none"
          stroke={ORANGE_COLOR}
          strokeWidth={RIBBON_STROKE_WIDTH}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={ORANGE_OPACITY}
          filter="url(#orange-glow)"
        />
      </svg>
    </div>
  );
}

export default SotlasFlowBackground;
