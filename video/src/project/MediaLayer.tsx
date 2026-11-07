import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, staticFile } from "remotion";
import type { PreparedMedia } from "./types";

export const MediaLayer: React.FC<{
  media: PreparedMedia;
  fit?: "cover" | "contain";
  volume?: number;
}> = ({ media, fit = "contain", volume = 1 }) => (
  <AbsoluteFill>
    {media.video ? (
      <OffthreadVideo
        src={staticFile(media.video)}
        muted
        style={{ width: "100%", height: "100%", objectFit: fit }}
      />
    ) : null}
    {media.audio ? <Audio src={staticFile(media.audio)} volume={volume} /> : null}
  </AbsoluteFill>
);
