import React from "react";
import { Composition } from "remotion";
import { Trailer, TRAILER_DURATION } from "./Trailer";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Trailer"
      component={Trailer}
      durationInFrames={TRAILER_DURATION}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
