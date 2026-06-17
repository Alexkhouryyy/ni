import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CountUp } from "../components/CountUp";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const StatScene: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [192, 210], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const andCountingOpacity = interpolate(frame, [170, 182], [0, 1], {
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
      <div style={{ marginBottom: 56, textAlign: "center" }}>
        <Title delay={6} size={72} color={COLORS.inkDim} weight={600}>
          By the numbers.
        </Title>
      </div>

      <div
        style={{
          display: "flex",
          gap: 48,
          alignItems: "stretch",
        }}
      >
        <CountUp
          end={2341}
          label="Sessions Remembered"
          accent={COLORS.blue}
          delay={30}
          duration={80}
        />
        <CountUp
          end={12}
          label="Skills Auto-Written"
          suffix="+"
          accent={COLORS.green}
          delay={70}
          duration={60}
        />
        <CountUp
          end={847}
          label="Facts in Memory"
          accent={COLORS.purple}
          delay={110}
          duration={70}
        />
      </div>

      <div
        style={{
          marginTop: 52,
          fontFamily: FONT,
          fontSize: 40,
          fontWeight: 800,
          letterSpacing: -1,
          color: COLORS.ink,
          opacity: andCountingOpacity,
        }}
      >
        And counting.
      </div>
    </AbsoluteFill>
  );
};
