import { AbsoluteFill, Sequence } from 'remotion';
import { Scene01_Problem } from './scenes/Scene01_Problem';
import { Scene02_Shift } from './scenes/Scene02_Shift';
import { Scene03_Features } from './scenes/Scene03_Features';
import { Scene04_Demo } from './scenes/Scene04_Demo';
import { Scene05_Tagline } from './scenes/Scene05_Tagline';
import { Scene06_EndCard } from './scenes/Scene06_EndCard';

export const StudyModeTrailer: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Scene 01: frames 0–150 */}
      <Sequence from={0} durationInFrames={150} premountFor={0}>
        <Scene01_Problem />
      </Sequence>

      {/* Scene 02: frames 150–270 */}
      <Sequence from={150} durationInFrames={120} premountFor={30}>
        <Scene02_Shift />
      </Sequence>

      {/* Scene 03: frames 270–390 */}
      <Sequence from={270} durationInFrames={120} premountFor={30}>
        <Scene03_Features />
      </Sequence>

      {/* Scene 04: frames 390–480 */}
      <Sequence from={390} durationInFrames={90} premountFor={30}>
        <Scene04_Demo />
      </Sequence>

      {/* Scene 05: frames 480–570 */}
      <Sequence from={480} durationInFrames={90} premountFor={30}>
        <Scene05_Tagline />
      </Sequence>

      {/* Scene 06: frames 570–600 */}
      <Sequence from={570} durationInFrames={30} premountFor={30}>
        <Scene06_EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
