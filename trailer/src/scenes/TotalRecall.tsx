import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CountUp } from "../components/CountUp";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const TotalRecall: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [192, 210], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bottomOpacity = interpolate(frame, [175, 188], [0, 1], {
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
      <div style={{ marginBottom: 52, textAlign: "center" }}>
        <Title delay={6} size={92} color={COLORS.ink} weight={900}>
          Total Recall
        </Title>
        <Title delay={22} size={40} color={COLORS.inkDim} weight={500}>
          It never forgets. Not a single word.
        </Title>
      </div>

      {/* Three counters */}
      <div
        style={{
          display: "flex",
          gap: 40,
          alignItems: "stretch",
        }}
      >
        <CountUp
          end={2341}
          label="conversations"
          accent={COLORS.blue}
          delay={40}
          duration={80}
        />
        <CountUp
          end={847}
          label="facts memorized"
          accent={COLORS.cyan}
          delay={75}
          duration={80}
        />
        <CountUp
          end={94}
          label="files indexed"
          accent={COLORS.purple}
          delay={110}
          duration={70}
        />
      </div>

      {/* Bottom line */}
      <div
        style={{
          marginTop: 48,
          fontFamily: FONT,
          fontSize: 36,
          fontWeight: 700,
          letterSpacing: 3,
          color: COLORS.blue,
          textTransform: "uppercase",
          opacity: bottomOpacity,
          textShadow: `0 0 40px ${COLORS.blue}55`,
        }}
      >
        Zero things forgotten.
      </div>
    </AbsoluteFill>
  );
};
