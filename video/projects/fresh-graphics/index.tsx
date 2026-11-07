import { Composition, registerRoot } from "remotion";
import { Film } from "./Composition";
import config from "./project.json";
import media from "./media.json";

const Root = () => (
  <Composition
    id="Reel"
    component={Film}
    durationInFrames={media.durationInFrames ?? config.durationInFrames}
    fps={config.fps}
    width={config.width}
    height={config.height}
  />
);

registerRoot(Root);
