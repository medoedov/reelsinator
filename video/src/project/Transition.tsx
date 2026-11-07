import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { EASE } from "../ui/Panel";

export const Fade: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  inFrames?: number;
  outFrames?: number;
}> = ({ children, durationInFrames, inFrames = 8, outFrames = 8 }) => {
  const frame = useCurrentFrame();
  const enter = inFrames > 0 ? interpolate(frame, [0, inFrames], [0, 1], EASE) : 1;
  const exit = outFrames > 0
    ? interpolate(frame, [Math.max(0, durationInFrames - outFrames), durationInFrames], [1, 0], EASE)
    : 1;
  return <AbsoluteFill style={{ opacity: enter * exit }}>{children}</AbsoluteFill>;
};
