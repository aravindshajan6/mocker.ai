"use client";

import { animate, createTimeline, stagger } from "animejs";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

export type Mood = "idle" | "happy" | "oops" | "celebrate" | "think" | "wave" | "sleepy";

type Props = { mood?: Mood; size?: number; className?: string; trigger?: number };

/**
 * Kunju — a small, round Kerala elephant who cheers you on.
 * Pure SVG animated with anime.js; every part is a <g> we can move independently.
 */
export default function Mascot({ mood = "idle", size = 140, className = "", trigger = 0 }: Props) {
  const root = useRef<SVGSVGElement>(null);
  const idleAnim = useRef<ReturnType<typeof animate> | null>(null);
  // anime.js writes inline transforms, which the CSS reduced-motion rules cannot reach — so the
  // looping idle animation and the mood reactions have to opt out here, explicitly.
  const still = useReducedMotion();

  // Breathing + blinking runs forever underneath everything else.
  useEffect(() => {
    const el = root.current;
    if (!el || still) return;
    const body = el.querySelector<SVGGElement>(".k-body")!;
    const eyes = el.querySelectorAll<SVGGElement>(".k-eye");
    const leftEar = el.querySelector<SVGGElement>(".k-ear-l")!;
    const rightEar = el.querySelector<SVGGElement>(".k-ear-r")!;
    idleAnim.current = animate(body, { translateY: [0, -3, 0], duration: 2600, ease: "inOutSine", loop: true });
    let alive = true;
    const blink = () => {
      if (!alive) return;
      animate(eyes, { scaleY: [1, 0.1, 1], duration: 180, ease: "inOutQuad" });
      setTimeout(blink, 2200 + Math.random() * 2600);
    };
    const flap = () => {
      if (!alive) return;
      animate(leftEar, { rotate: [0, -10, 0], duration: 600, ease: "inOutSine" });
      animate(rightEar, { rotate: [0, 10, 0], duration: 600, ease: "inOutSine" });
      setTimeout(flap, 5000 + Math.random() * 5000);
    };
    const t1 = setTimeout(blink, 1200);
    const t2 = setTimeout(flap, 2500);
    return () => {
      alive = false;
      clearTimeout(t1);
      clearTimeout(t2);
      idleAnim.current?.cancel();
    };
  }, [still]);

  // Mood reactions. `trigger` lets the parent replay the same mood (e.g. two correct answers in a row).
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const all = el.querySelector<SVGGElement>(".k-all")!;
    const trunk = el.querySelector<SVGGElement>(".k-trunk")!;
    const mouthHappy = el.querySelector<SVGPathElement>(".k-mouth-happy")!;
    const mouthSad = el.querySelector<SVGPathElement>(".k-mouth-sad")!;
    const mouthFlat = el.querySelector<SVGPathElement>(".k-mouth-flat")!;
    const eyesOpen = el.querySelectorAll<SVGGElement>(".k-eye");
    const eyesHappy = el.querySelectorAll<SVGPathElement>(".k-eye-happy");
    const cheeks = el.querySelectorAll<SVGCircleElement>(".k-cheek");
    const ears = el.querySelectorAll<SVGGElement>(".k-ear");
    const zzz = el.querySelector<SVGGElement>(".k-zzz")!;
    const lids = el.querySelectorAll<SVGRectElement>(".k-lid");

    const show = (node: Element | NodeListOf<Element>, v: boolean) => {
      const list = "length" in node ? Array.from(node) : [node];
      list.forEach((n) => ((n as SVGElement).style.opacity = v ? "1" : "0"));
    };
    // reset
    show(mouthHappy, mood === "happy" || mood === "celebrate" || mood === "wave");
    show(mouthSad, mood === "oops");
    show(mouthFlat, mood === "idle" || mood === "think" || mood === "sleepy");
    show(eyesHappy, mood === "celebrate");
    show(eyesOpen, mood !== "celebrate");
    show(zzz, mood === "sleepy");
    show(lids, mood === "sleepy");
    show(cheeks, mood === "happy" || mood === "celebrate");
    // The expression above is opacity only, so it still reads under reduced motion — Kunju keeps
    // smiling or drooping at the answer. It is the hopping and wobbling below that we drop.
    if (still) {
      all.style.transform = "none";
      trunk.style.transform = "none";
      return;
    }
    animate(all, { rotate: 0, translateX: 0, translateY: 0, scale: 1, duration: 200 });
    animate(trunk, { rotate: 0, duration: 200 });

    if (mood === "happy") {
      createTimeline()
        .add(all, { translateY: [0, -14, 0], scaleX: [1, 0.96, 1.04, 1], scaleY: [1, 1.06, 0.96, 1], duration: 520, ease: "outQuad" })
        .add(trunk, { rotate: [0, -28, -20, -28, 0], duration: 700, ease: "inOutSine" }, "-=380");
      animate(cheeks, { scale: [0.6, 1.15, 1], duration: 400, ease: "outBack" });
    } else if (mood === "oops") {
      createTimeline()
        .add(all, { rotate: [0, -6, 4, -3, 0], duration: 600, ease: "inOutSine" })
        .add(trunk, { rotate: [0, 18, 14], duration: 400, ease: "outQuad" }, "-=500")
        .add(ears, { rotate: [0, 0], duration: 10 });
    } else if (mood === "celebrate") {
      createTimeline({ loop: 2 })
        .add(all, { translateY: [0, -22, 0], rotate: [0, -8, 8, 0], duration: 620, ease: "outQuad" })
        .add(trunk, { rotate: [0, -40, -30, -40, 0], duration: 620, ease: "inOutSine" }, 0)
        .add(ears[0], { rotate: [0, -22, 0], duration: 620, ease: "inOutSine" }, 0)
        .add(ears[1], { rotate: [0, 22, 0], duration: 620, ease: "inOutSine" }, 0);
    } else if (mood === "think") {
      animate(trunk, { rotate: [0, 8, 0], duration: 1800, ease: "inOutSine", loop: true, alternate: true });
      animate(eyesOpen, { translateX: [0, 2, 0, -2, 0], duration: 3000, ease: "inOutSine", loop: true });
    } else if (mood === "wave") {
      animate(trunk, { rotate: [0, -30, 0, -30, 0], duration: 1100, ease: "inOutSine" });
      animate(all, { rotate: [0, -3, 3, 0], duration: 900, ease: "inOutSine" });
    } else if (mood === "sleepy") {
      animate(zzz.querySelectorAll("text"), { translateY: [0, -10], opacity: [0, 1, 0], duration: 2400, delay: stagger(500), loop: true, ease: "inOutSine" });
      animate(all, { rotate: [0, 3], duration: 1500, ease: "inOutSine", loop: true, alternate: true });
    }
  }, [mood, trigger, still]);

  return (
    <svg
      ref={root}
      viewBox="0 0 200 200"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label="Kunju the scholar elephant, your study buddy"
    >
      <g className="k-all mascot-part">
        <g className="k-body mascot-part">
          {/* ears */}
          <g className="k-ear k-ear-l mascot-part" style={{ transformOrigin: "78px 96px" }}>
            <ellipse cx="46" cy="98" rx="34" ry="40" fill="#7fb8a8" />
            <ellipse cx="50" cy="100" rx="22" ry="28" fill="#f3b7a6" opacity="0.7" />
          </g>
          <g className="k-ear k-ear-r mascot-part" style={{ transformOrigin: "122px 96px" }}>
            <ellipse cx="154" cy="98" rx="34" ry="40" fill="#7fb8a8" />
            <ellipse cx="150" cy="100" rx="22" ry="28" fill="#f3b7a6" opacity="0.7" />
          </g>
          {/* head */}
          <circle cx="100" cy="104" r="62" fill="#9ccfc0" />
          <circle cx="100" cy="104" r="62" fill="url(#k-shade)" />
          {/* tuft */}
          <path d="M92 44 q8 -14 16 0" stroke="#3d6e62" strokeWidth="4" fill="none" strokeLinecap="round" />
          {/* graduation cap — the scholar's mortarboard, tassel in the app's accent orange */}
          <g className="k-cap">
            <path d="M100 27 L141 43 L100 59 L59 43 Z" fill="#2c4f5e" />
            <path d="M100 43 q22 2 24 20" stroke="#e8952a" strokeWidth="3" fill="none" strokeLinecap="round" />
            <circle cx="124" cy="65" r="4" fill="#e8952a" />
            <circle cx="100" cy="43" r="3.2" fill="#e8952a" />
          </g>
          {/* cheeks */}
          <circle className="k-cheek mascot-part" cx="66" cy="118" r="8" fill="#f59f8f" opacity="0" />
          <circle className="k-cheek mascot-part" cx="134" cy="118" r="8" fill="#f59f8f" opacity="0" />
          {/* eyes */}
          <g className="k-eye mascot-part">
            <circle cx="80" cy="96" r="7" fill="#1f2a37" />
            <circle cx="82.5" cy="93.5" r="2.4" fill="#fff" />
          </g>
          <g className="k-eye mascot-part">
            <circle cx="120" cy="96" r="7" fill="#1f2a37" />
            <circle cx="122.5" cy="93.5" r="2.4" fill="#fff" />
          </g>
          <path className="k-eye-happy" d="M72 97 q8 -9 16 0" stroke="#1f2a37" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0" />
          <path className="k-eye-happy" d="M112 97 q8 -9 16 0" stroke="#1f2a37" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0" />
          <rect className="k-lid" x="71" y="90" width="18" height="8" rx="4" fill="#9ccfc0" opacity="0" />
          <rect className="k-lid" x="111" y="90" width="18" height="8" rx="4" fill="#9ccfc0" opacity="0" />
          {/* study glasses — drawn over eyes and lids so the frames always sit on top */}
          <g className="k-glasses">
            <circle cx="80" cy="96" r="11.5" fill="none" stroke="#3d6e62" strokeWidth="3" />
            <circle cx="120" cy="96" r="11.5" fill="none" stroke="#3d6e62" strokeWidth="3" />
            <path d="M91.5 96 h17" stroke="#3d6e62" strokeWidth="3" strokeLinecap="round" />
          </g>
          {/* trunk */}
          <g className="k-trunk mascot-part" style={{ transformOrigin: "100px 112px" }}>
            <path d="M100 112 q-2 26 12 40 q10 10 20 4" stroke="#8ec4b4" strokeWidth="18" fill="none" strokeLinecap="round" />
            <path d="M100 112 q-2 26 12 40 q10 10 20 4" stroke="#3d6e62" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.15" strokeDasharray="0 14" />
          </g>
          {/* mouths */}
          <path className="k-mouth-flat" d="M84 134 q6 3 12 0" stroke="#3d6e62" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0" />
          <path className="k-mouth-happy" d="M80 132 q10 12 22 0" stroke="#3d6e62" strokeWidth="3.5" fill="none" strokeLinecap="round" opacity="0" />
          <path className="k-mouth-sad" d="M82 138 q9 -8 18 0" stroke="#3d6e62" strokeWidth="3.5" fill="none" strokeLinecap="round" opacity="0" />
          {/* zzz */}
          <g className="k-zzz" opacity="0" fill="#3d6e62" fontWeight="800" fontFamily="inherit">
            <text x="150" y="60" fontSize="16" className="mascot-part">z</text>
            <text x="162" y="46" fontSize="20" className="mascot-part">z</text>
            <text x="176" y="30" fontSize="24" className="mascot-part">z</text>
          </g>
        </g>
      </g>
      <defs>
        <radialGradient id="k-shade" cx="0.4" cy="0.35" r="0.8">
          <stop offset="0" stopColor="#fff" stopOpacity="0.25" />
          <stop offset="1" stopColor="#000" stopOpacity="0.08" />
        </radialGradient>
      </defs>
    </svg>
  );
}
