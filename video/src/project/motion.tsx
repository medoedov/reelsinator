import React from "react";
import { Easing, interpolate } from "remotion";

export const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const EASE = { ...CLAMP, easing: Easing.out(Easing.cubic) } as const;

/**
 * Masked reveal: the line rises out from behind a hard edge instead of fading in.
 * This is the single biggest "expensive vs template" tell in motion design — a fade says
 * nothing about the type, a mask makes the letterforms perform.
 * `progress` 0→1 drives it; `delay` is in frames and handled by the caller.
 */
export const Reveal: React.FC<{
  progress: number;
  children: React.ReactNode;
  distance?: number;
  /** vertical bleed of the mask in em — raise it for faces whose descenders exceed the line box */
  pad?: number;
  /** the em the bleeds are measured in, px. Without it the wrapper inherits 16px and a 100px
   *  word gets a 2px side bleed, so the mask shaves its glyphs */
  size?: number;
}> = ({ progress, children, distance = 1.0, pad = 0.12, size }) => (
  // The mask bleeds sideways so it only ever clips vertically — a glyph's side bearing must
  // never be shaved off by the reveal box (CSS can't do overflow-y-only).
  <div
    style={{
      overflow: "hidden",
      fontSize: size,
      // the bleeds are cancelled by negative margins, so the mask never changes the layout —
      // a padded box pushes the next caption line down by the whole pad
      paddingBottom: `${pad}em`,
      marginBottom: `${-pad}em`,
      paddingTop: `${pad / 2}em`,
      marginTop: `${-pad / 2}em`,
      marginInline: "-0.15em",
      paddingInline: "0.15em",
      // never let a flex row shrink the mask box below its text — a phrase that fills the
      // title-safe width otherwise loses its last glyph
      flexShrink: 0,
    }}
  >
    <div
      style={{
        transform: `translateY(${interpolate(progress, [0, 1], [100 * distance, 0], CLAMP)}%)`,
        opacity: interpolate(progress, [0, 0.35], [0, 1], CLAMP),
      }}
    >
      {children}
    </div>
  </div>
);
