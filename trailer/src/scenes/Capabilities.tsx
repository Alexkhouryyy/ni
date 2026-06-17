import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import { FeatureCard } from "../components/FeatureCard";
import { COLORS } from "../theme";

// Four capabilities, each on screen ~55 frames, sliding in sequentially.
const FEATURES = [
  {
    glyph: "⚡",
    title: "Autonomous Cortex",
    sub: "Works toward your goals while you sleep.",
    accent: COLORS.amber,
  },
  {
    glyph: "\u{1F9E0}",
    title: "Total Recall",
    sub: "Remembers everything it ever perceived.",
    accent: COLORS.cyan,
  },
  {
    glyph: "\u{1F6E0}",
    title: "Self-Extending",
    sub: "Writes its own tools when it lacks one.",
    accent: COLORS.green,
  },
  {
    glyph: "\u{1F578}",
    title: "Second Brain",
    sub: "Your knowledge, as a living graph.",
    accent: COLORS.purple,
  },
];

const ONE = 56;

const Slide: React.FC<{ index: number }> = ({ index }) => {
  const frame = useCurrentFrame();
  const f = FEATURES[index];
  // Fade each card out in its last 10 frames.
  const out = interpolate(frame, [ONE - 12, ONE - 2], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center", opacity: out }}
    >
      <div style={{ width: 1180 }}>
        <FeatureCard glyph={f.glyph} title={f.title} sub={f.sub} accent={f.accent} delay={0} />
      </div>
    </AbsoluteFill>
  );
};

export const Capabilities: React.FC = () => {
  return (
    <AbsoluteFill>
      {FEATURES.map((_, i) => (
        <Sequence key={i} from={i * ONE} durationInFrames={ONE}>
          <Slide index={i} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const CAPABILITIES_DURATION = FEATURES.length * ONE;
