import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { EASE, Reveal } from "../../src/ui/Panel";
import { MediaLayer } from "../../src/project/MediaLayer";
import { CaptionTrack } from "../../src/project/CaptionTrack";
import config from "./project.json";
import media from "./media.json";

export const Film = () => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const size = Math.min(width * 0.078, height * 0.12);
  const reveal = interpolate(frame, [0, fps * 0.65], [0, 1], EASE);
  return (
    <AbsoluteFill style={{ backgroundColor: config.colors.background, fontFamily: config.fontFamily, color: config.colors.foreground }}>
      <MediaLayer media={media} />
      {!media.video ? (
        <AbsoluteFill style={{ justifyContent: "center", padding: width * 0.09 }}>
          <div style={{ width: size * 0.7, height: size * 0.1, background: config.colors.accent, marginBottom: size * 0.6 }} />
          <Reveal progress={reveal} size={size} pad={0.18}>
            <div style={{ fontWeight: 700, fontSize: size, lineHeight: 1.08, letterSpacing: "-0.045em" }}>{config.title}</div>
          </Reveal>
          <div style={{ fontSize: size * 0.35, color: config.colors.muted, marginTop: size * 0.45, maxWidth: width * 0.72, lineHeight: 1.4 }}>{config.idea}</div>
        </AbsoluteFill>
      ) : null}
      <CaptionTrack words={media.captions} fontFamily={config.fontFamily} color={config.colors.foreground} accent={config.colors.accent} />
    </AbsoluteFill>
  );
};
