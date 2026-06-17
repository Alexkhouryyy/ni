import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const AlwaysOn: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [162, 180], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const taglineOpacity = interpolate(frame, [115, 130], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: sceneOut,
        flexDirection: "column",
        gap: 0,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          alignItems: "center",
        }}
      >
        <Title delay={4} size={100} color={COLORS.ink} weight={900}>
          Always on.
        </Title>

        <Title delay={30} size={58} color={COLORS.inkDim} weight={600}>
          On your laptop.
        </Title>
        <Title delay={54} size={58} color={COLORS.inkDim} weight={600}>
          On your phone.
        </Title>
        <Title delay={78} size={58} color={COLORS.inkDim} weight={600}>
          In the cloud.
        </Title>
      </div>

      <div
        style={{
          marginTop: 36,
          fontFamily: FONT,
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 4,
          color: COLORS.blue,
          textTransform: "uppercase",
          opacity: taglineOpacity,
          textShadow: `0 0 30px ${COLORS.blue}55`,
        }}
      >
        Never offline. Never waiting.
      </div>
    </AbsoluteFill>
  );
};
