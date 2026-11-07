import React, { useMemo } from "react";
import { measureText } from "@remotion/layout-utils";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, EASE, Reveal } from "../ui/Panel";
import type { CaptionWord } from "./types";

const groupWords = (words: CaptionWord[]): CaptionWord[][] => {
  const groups: CaptionWord[][] = [];
  for (const word of words) {
    const group = groups[groups.length - 1];
    const last = group?.[group.length - 1];
    const short = word.w.length <= 2 && word.em === 0;
    if (
      !group ||
      group.length >= 4 ||
      (group.length === 3 && short) ||
      (last && (/[.!?…]$/.test(last.w) || word.s - last.e > 0.45))
    ) {
      groups.push([word]);
    } else {
      group.push(word);
    }
  }
  return groups;
};

export const CaptionTrack: React.FC<{
  words: CaptionWord[];
  fontFamily?: string;
  fontSize?: number;
  color?: string;
  accent?: string;
  background?: string;
  position?: "bottom" | "top" | "center";
  inset?: number;
}> = ({
  words,
  fontFamily = "Arial",
  fontSize,
  color = "#ffffff",
  accent = "#9db7ff",
  background = "rgba(9, 13, 22, 0.88)",
  position = "bottom",
  inset = 0.15,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const groups = useMemo(() => groupWords(words), [words]);
  const requestedSize = fontSize ?? Math.min(width * 0.057, height * 0.075);
  const maxWidth = width * 0.82;
  const size = useMemo(() => {
    const widest = Math.max(
      1,
      ...groups.map((group) =>
        measureText({
          text: group.map((word) => word.w).join(" "),
          fontFamily,
          fontWeight: "700",
          fontSize: requestedSize,
        }).width,
      ),
    );
    return requestedSize * Math.min(1, maxWidth / widest);
  }, [groups, fontFamily, requestedSize, maxWidth]);

  const time = frame / fps;
  const group = groups.find((candidate, index) => {
    const end = Math.min(
      candidate[candidate.length - 1].e + 0.16,
      groups[index + 1]?.[0].s ?? Infinity,
    );
    return time >= candidate[0].s && time < end;
  });
  if (!group) return null;
  const progress = interpolate(frame - group[0].s * fps, [0, Math.max(1, fps * 0.09)], [0, 1], EASE);
  const end = group[group.length - 1].e + 0.16;
  const opacity = interpolate(time, [end - 0.1, end], [1, 0], CLAMP);

  return (
    <div
      style={{
        position: "absolute",
        left: width * 0.07,
        right: width * 0.07,
        ...(position === "bottom"
          ? { bottom: height * inset }
          : position === "top"
            ? { top: height * inset }
            : { top: height * 0.5, transform: "translateY(-50%)" }),
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <Reveal progress={progress} size={size} pad={0.3}>
        <div
          style={{
            fontFamily,
            fontWeight: 700,
            fontSize: size,
            lineHeight: 1.25,
            whiteSpace: "nowrap",
            background,
            padding: "0.18em 0.42em 0.22em",
            borderRadius: size * 0.17,
          }}
        >
          {group.map((word, index) => (
            <React.Fragment key={`${word.s}-${index}`}>
              {index ? " " : null}
              <span style={{ color: time >= word.s && time < word.e ? accent : color }}>{word.w}</span>
            </React.Fragment>
          ))}
        </div>
      </Reveal>
    </div>
  );
};
