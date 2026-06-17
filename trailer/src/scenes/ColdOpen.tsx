import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Title } from "../components/Text";
import { COLORS } from "../theme";

// "Most assistants wait. / Yours shouldn't." — establish the premise.
export const ColdOpen: React.FC = () => {
  const frame = useCurrentFrame();
  // Fade the whole scene out near its end for a clean cut.
  const out = interpolate(frame, [62, 75], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: out,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <Title delay={6} size={76} color={COLORS.inkDim} weight={600}>
          Every AI assistant waits to be asked.
        </Title>
        <Title delay={34} size={92} color={COLORS.ink}>
          This one doesn&apos;t.
        </Title>
      </div>
    </AbsoluteFill>
  );
};
