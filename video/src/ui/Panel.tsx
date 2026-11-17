import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { BRAND, PACE, STYLE, rgba } from "../brand";

import { CLAMP, EASE } from "../project/motion";
export { CLAMP, EASE, Reveal } from "../project/motion";

// the user's pace (harness.config.json → style.motion.pace) scales every entry and cascade
export const ENTER = Math.round(15 * PACE); // 500ms at «normal»
export const CASCADE = Math.max(1, Math.round(3 * PACE)); // ~100ms between elements

/** progress 0 -> 1 -> 0. Drives the panel and every element inside it. */
export const usePanelProgress = (exitStart: number, exitEnd: number) => {
  const frame = useCurrentFrame();
  return (
    interpolate(frame, [0, ENTER], [0, 1], EASE) *
    interpolate(frame, [exitStart, exitEnd], [1, 0], EASE)
  );
};

/** One type scale for the whole video. */
export const TYPE = {
  headline: {
    fontFamily: BRAND.text,
    fontWeight: 700,
    fontSize: 84,
    lineHeight: 1.1,
    letterSpacing: "-0.03em",
    color: BRAND.light,
  },
  sub: {
    fontFamily: BRAND.text,
    fontWeight: 500,
    fontSize: 44,
    lineHeight: 1.25,
    letterSpacing: "-0.01em",
    color: BRAND.light,
  },
  label: {
    fontFamily: BRAND.text,
    fontWeight: 600,
    fontSize: 32,
    lineHeight: 1.1,
    letterSpacing: "-0.01em",
    color: BRAND.light,
  },
} as const;

/** Frame-driven progress for one element in a cascade. */
export const useReveal = (delay: number, duration = ENTER) => {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, duration], [0, 1], EASE);
};

/**
 * Exit hierarchy: the content leaves one cascade step (100ms) before the panel does, so the
 * card empties and *then* closes instead of everything vanishing on the same frame.
 */
export const useExit = (exitStart: number, exitEnd: number) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [exitStart - CASCADE, exitEnd - CASCADE], [1, 0], EASE);
};

export const Panel: React.FC<{
  progress: number;
  children: React.ReactNode;
}> = ({ progress, children }) => {
  const frame = useCurrentFrame();
  // a slow linear drift (~1.5% over 3s) so a card that has landed doesn't freeze; «calm» pace
  // drifts slower
  const drift = 1 + (frame * 0.00016) / PACE;
  const enter = interpolate(progress, [0, 1], [0.95, 1], CLAMP);
  // Depth: the blur and shadow ease in with the panel instead of snapping on at frame 0.
  const blur = interpolate(progress, [0, 1], [0, 28], CLAMP);

  // style.cards: «glass» = a translucent tint of the dark colour over a backdrop blur with a
  // hairline edge; «solid» = an opaque plate in the dark colour. Either way the shadow is wide
  // and soft so the card lifts off the footage.
  const glass = STYLE.cards === "glass";
  return (
    <div
      style={{
        borderRadius: 40,
        padding: "52px 56px",
        backgroundColor: glass ? rgba(BRAND.dark, 0.46) : BRAND.dark,
        backgroundImage: glass
          ? "linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.03) 45%, rgba(255,255,255,0) 100%)"
          : undefined,
        backdropFilter: glass ? `blur(${blur * 1.6}px) saturate(1.3)` : undefined,
        boxShadow: glass
          ? "inset 0 1px 0 rgba(255,255,255,0.28), inset 0 0 0 1px rgba(255,255,255,0.12), 0 24px 70px rgba(0,0,0,0.32)"
          : "0 24px 70px rgba(0,0,0,0.32)",
        opacity: progress,
        transform: `scale(${enter * drift}) translateY(${interpolate(progress, [0, 1], [14, 0], CLAMP)}px)`,
        transformOrigin: "50% 0%",
      }}
    >
      {children}
    </div>
  );
};

export default Panel;
