export type CaptionWord = {
  w: string;
  s: number;
  e: number;
  em?: number;
  accent?: number;
};

export type PreparedMedia = {
  durationInFrames?: number | null;
  video: string | null;
  audio: string | null;
  captions: CaptionWord[];
  splices: number[];
  fingerprint?: string | null;
};

export type ProjectColors = {
  background: string;
  foreground: string;
  accent: string;
  muted: string;
};
