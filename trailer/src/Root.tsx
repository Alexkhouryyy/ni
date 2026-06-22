import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { StudyModeTrailer } from './StudyModeTrailer';
import { StudyModeTrailerV2 } from './StudyModeTrailerV2';
import { ModesShowcaseTrailer } from './ModesShowcaseTrailer';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="StudyModeTrailer"
        component={StudyModeTrailer}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="StudyModeV2"
        component={StudyModeTrailerV2}
        durationInFrames={3600}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="ModesShowcase"
        component={ModesShowcaseTrailer}
        durationInFrames={5400}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};

registerRoot(RemotionRoot);
