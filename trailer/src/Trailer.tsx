import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Background } from "./components/Background";
import { ColdOpen } from "./scenes/ColdOpen";
import { LogoReveal } from "./scenes/LogoReveal";
import { Capabilities } from "./scenes/Capabilities";
import { Pillars } from "./scenes/Pillars";
import { AlwaysOn } from "./scenes/AlwaysOn";
import { CloseLogo } from "./scenes/CloseLogo";

// Scenes overlap by OVERLAP frames so the out-fade of one crossfades into the
// in-fade of the next (no black flash between cuts).
const OVERLAP = 10;

const SCENES: { comp: React.FC; dur: number }[] = [
  { comp: ColdOpen, dur: 75 },
  { comp: LogoReveal, dur: 90 },
  { comp: Capabilities, dur: 224 },
  { comp: Pillars, dur: 84 },
  { comp: AlwaysOn, dur: 70 },
  { comp: CloseLogo, dur: 88 },
];

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
