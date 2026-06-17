import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { PunchWord } from "../components/Text";
import { COLORS } from "../theme";

// Four power words punch in one after another.
export const Pillars: React.FC = () => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [70, 84], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: out,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        <PunchWord delay={4} color={COLORS.blue}>
          Voice.
        </PunchWord>
        <PunchWord delay={18} color={COLORS.cyan}>
          Vision.
        </PunchWord>
        <PunchWord delay={32} color={COLORS.green}>
          Memory.
        </PunchWord>
        <PunchWord delay={46} color={COLORS.amber}>
          Autonomy.
        </PunchWord>
      </div>
    </AbsoluteFill>
  );
};
