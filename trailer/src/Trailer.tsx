import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Background } from "./components/Background";
import { DarkOpening } from "./scenes/DarkOpening";
import { LogoReveal } from "./scenes/LogoReveal";
import { AutoCortex } from "./scenes/AutoCortex";
import { VoiceVision } from "./scenes/VoiceVision";
import { TotalRecall } from "./scenes/TotalRecall";
import { SkillForge } from "./scenes/SkillForge";
import { SecondBrain } from "./scenes/SecondBrain";
import { CapGrid } from "./scenes/CapGrid";
import { Pillars } from "./scenes/Pillars";
import { AlwaysOn } from "./scenes/AlwaysOn";
import { StatScene } from "./scenes/StatScene";
import { CloseLogo } from "./scenes/CloseLogo";

// Scenes overlap by OVERLAP frames so the out-fade of one crossfades into the
// in-fade of the next — no black flash between cuts.
const OVERLAP = 12;

const SCENES: { comp: React.FC; dur: number }[] = [
  { comp: DarkOpening, dur: 120 },   // 4.0s  — dramatic cold open
  { comp: LogoReveal, dur: 180 },    // 6.0s  — logo + brand
  { comp: AutoCortex, dur: 240 },    // 8.0s  — autonomous tasks while you sleep
  { comp: VoiceVision, dur: 210 },   // 7.0s  — voice + vision chat demo
  { comp: TotalRecall, dur: 210 },   // 7.0s  — memory / recall counters
  { comp: SkillForge, dur: 240 },    // 8.0s  — self-writing tools
  { comp: SecondBrain, dur: 180 },   // 6.0s  — Obsidian vault / knowledge graph
  { comp: CapGrid, dur: 270 },       // 9.0s  — 6-card capability grid
  { comp: Pillars, dur: 180 },       // 6.0s  — Voice. Vision. Memory. Autonomy.
  { comp: AlwaysOn, dur: 180 },      // 6.0s  — cross-platform, never offline
  { comp: StatScene, dur: 210 },     // 7.0s  — animated stat counters
  { comp: CloseLogo, dur: 240 },     // 8.0s  — grand finale
];
// Total raw: 2460f  Overlaps: 11×12=132  Net: 2328f ≈ 77.6 seconds

// Precompute the start frame of each scene.
const STARTS: number[] = [];
SCENES.reduce((acc, s, i) => {
  STARTS[i] = acc;
  return acc + s.dur - OVERLAP;
}, 0);

export const TRAILER_DURATION =
  STARTS[SCENES.length - 1] + SCENES[SCENES.length - 1].dur;

export const Trailer: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#04060d" }}>
      <Background />
      {SCENES.map(({ comp: Comp, dur }, i) => (
        <Sequence key={i} from={STARTS[i]} durationInFrames={dur}>
          <Comp />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
