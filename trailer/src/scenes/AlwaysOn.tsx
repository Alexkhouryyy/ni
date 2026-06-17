import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Title } from "../components/Text";
import { COLORS } from "../theme";

export const AlwaysOn: React.FC = () => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [58, 70], [1, 0], {
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
      <div style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "center" }}>
        <Title delay={4} size={96} color={COLORS.ink}>
          Always on.
        </Title>
        <Title delay={22} size={64} color={COLORS.inkDim} weight={500}>
          On your laptop, your phone, the cloud — everywhere you are.
        </Title>
      </div>
    </AbsoluteFill>
  );
};
