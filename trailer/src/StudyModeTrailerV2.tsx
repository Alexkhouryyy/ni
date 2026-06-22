import React from 'react';
import { Audio, Sequence, staticFile } from 'remotion';
import { V2_Scene01_Problem } from './scenes/v2/V2_Scene01_Problem';
import { V2_Scene02_Challenge } from './scenes/v2/V2_Scene02_Challenge';
import { V2_Scene03_Reveal } from './scenes/v2/V2_Scene03_Reveal';
import { V2_Scene04_Transform } from './scenes/v2/V2_Scene04_Transform';
import { V2_Scene05_Demo1 } from './scenes/v2/V2_Scene05_Demo1';
import { V2_Scene06_Demo2 } from './scenes/v2/V2_Scene06_Demo2';
import { V2_Scene07_Demo3 } from './scenes/v2/V2_Scene07_Demo3';
import { V2_Scene09_Philosophy } from './scenes/v2/V2_Scene09_Philosophy';
import { V2_Scene10_EndCard } from './scenes/v2/V2_Scene10_EndCard';
import { V2_SceneUC0_UseCasesIntro } from './scenes/v2/V2_SceneUC0_UseCasesIntro';
import { V2_SceneUC1_UseCaseCoding } from './scenes/v2/V2_SceneUC1_UseCaseCoding';
import { V2_SceneUC2_UseCaseMath } from './scenes/v2/V2_SceneUC2_UseCaseMath';
import { V2_SceneUC3_UseCaseHistory } from './scenes/v2/V2_SceneUC3_UseCaseHistory';
import { V2_SceneUC4_UseCasesBanner } from './scenes/v2/V2_SceneUC4_UseCasesBanner';

/**
 * StudyModeTrailerV2 — 120-second JARVIS Study Mode trailer
 *
 * Total: 3600 frames @ 30fps = 120 seconds
 *
 * Scene layout:
 *   Scene 01: Problem          from=0     duration=270
 *   Scene 02: Challenge        from=270   duration=270
 *   Scene 03: Reveal           from=540   duration=270
 *   Scene 04: Transform        from=810   duration=270
 *   Scene 05: Demo1 Socratic   from=1080  duration=360
 *   Scene 06: Demo2 Refusal    from=1440  duration=360
 *   SceneUC0: UseCasesIntro    from=1800  duration=180
 *   SceneUC1: UseCaseCoding    from=1980  duration=300
 *   SceneUC2: UseCaseMath      from=2280  duration=300
 *   SceneUC3: UseCaseHistory   from=2580  duration=300
 *   SceneUC4: UseCasesBanner   from=2880  duration=180
 *   Scene 07: Demo3 Quiz       from=3060  duration=300
 *   Scene 09: Philosophy       from=3360  duration=180
 *   Scene 10: EndCard          from=3540  duration=60
 */
export const StudyModeTrailerV2: React.FC = () => {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: '#000000',
      overflow: 'hidden',
    }}>
      {/* Narration audio — full duration */}
      <Audio
        src={staticFile('audio/narration.mp3')}
        volume={1}
      />

      {/* Scene 01 — The Problem (0–270) */}
      <Sequence from={0} durationInFrames={270}>
        <V2_Scene01_Problem />
      </Sequence>

      {/* Scene 02 — The Challenge (270–540) */}
      <Sequence from={270} durationInFrames={270}>
        <V2_Scene02_Challenge />
      </Sequence>

      {/* Scene 03 — The Reveal (540–810) */}
      <Sequence from={540} durationInFrames={270}>
        <V2_Scene03_Reveal />
      </Sequence>

      {/* Scene 04 — The Transformation (810–1080) */}
      <Sequence from={810} durationInFrames={270}>
        <V2_Scene04_Transform />
      </Sequence>

      {/* Scene 05 — Demo: Socratic Question (1080–1440) */}
      <Sequence from={1080} durationInFrames={360}>
        <V2_Scene05_Demo1 />
      </Sequence>

      {/* Scene 06 — Demo: The Refusal (1440–1800) */}
      <Sequence from={1440} durationInFrames={360}>
        <V2_Scene06_Demo2 />
      </Sequence>

      {/* SceneUC0 — Use Cases Intro (1800–1980) */}
      <Sequence from={1800} durationInFrames={180}>
        <V2_SceneUC0_UseCasesIntro />
      </Sequence>

      {/* SceneUC1 — Use Case: Coding (1980–2280) */}
      <Sequence from={1980} durationInFrames={300}>
        <V2_SceneUC1_UseCaseCoding />
      </Sequence>

      {/* SceneUC2 — Use Case: Mathematics (2280–2580) */}
      <Sequence from={2280} durationInFrames={300}>
        <V2_SceneUC2_UseCaseMath />
      </Sequence>

      {/* SceneUC3 — Use Case: History (2580–2880) */}
      <Sequence from={2580} durationInFrames={300}>
        <V2_SceneUC3_UseCaseHistory />
      </Sequence>

      {/* SceneUC4 — Use Cases Banner (2880–3060) */}
      <Sequence from={2880} durationInFrames={180}>
        <V2_SceneUC4_UseCasesBanner />
      </Sequence>

      {/* Scene 07 — Demo: The Quiz (3060–3360) */}
      <Sequence from={3060} durationInFrames={300}>
        <V2_Scene07_Demo3 />
      </Sequence>

      {/* Scene 09 — Philosophy (3360–3540) */}
      <Sequence from={3360} durationInFrames={180}>
        <V2_Scene09_Philosophy />
      </Sequence>

      {/* Scene 10 — End Card (3540–3600) */}
      <Sequence from={3540} durationInFrames={60}>
        <V2_Scene10_EndCard />
      </Sequence>
    </div>
  );
};
