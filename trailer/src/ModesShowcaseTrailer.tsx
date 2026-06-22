import React from 'react';
import { Audio, Sequence, staticFile } from 'remotion';
import { MS_Intro } from './scenes/modes/MS_Intro';
import { MS_Focus } from './scenes/modes/MS_Focus';
import { MS_Brutal } from './scenes/modes/MS_Brutal';
import { MS_Health } from './scenes/modes/MS_Health';
import { MS_Debate } from './scenes/modes/MS_Debate';
import { MS_Executive } from './scenes/modes/MS_Executive';
import { MS_Venting } from './scenes/modes/MS_Venting';
import { MS_AllModes } from './scenes/modes/MS_AllModes';
import { MS_Outro } from './scenes/modes/MS_Outro';

// Total: 5400 frames = 3 min @ 30fps
// MS_Intro       from=0     dur=270   (9s)
// MS_Focus       from=270   dur=720   (24s)
// MS_Brutal      from=990   dur=720   (24s)
// MS_Health      from=1710  dur=720   (24s)
// MS_Debate      from=2430  dur=720   (24s)
// MS_Executive   from=3150  dur=720   (24s)
// MS_Venting     from=3870  dur=720   (24s)
// MS_AllModes    from=4590  dur=450   (15s)
// MS_Outro       from=5040  dur=360   (12s)

export const ModesShowcaseTrailer: React.FC = () => {
  return (
    <>
      {/* Narration audio — plays throughout */}
      <Audio src={staticFile('audio/modes_narration.mp3')} volume={1} />

      <Sequence from={0} durationInFrames={270}>
        <MS_Intro />
      </Sequence>

      <Sequence from={270} durationInFrames={720}>
        <MS_Focus />
      </Sequence>

      <Sequence from={990} durationInFrames={720}>
        <MS_Brutal />
      </Sequence>

      <Sequence from={1710} durationInFrames={720}>
        <MS_Health />
      </Sequence>

      <Sequence from={2430} durationInFrames={720}>
        <MS_Debate />
      </Sequence>

      <Sequence from={3150} durationInFrames={720}>
        <MS_Executive />
      </Sequence>

      <Sequence from={3870} durationInFrames={720}>
        <MS_Venting />
      </Sequence>

      <Sequence from={4590} durationInFrames={450}>
        <MS_AllModes />
      </Sequence>

      <Sequence from={5040} durationInFrames={360}>
        <MS_Outro />
      </Sequence>
    </>
  );
};
