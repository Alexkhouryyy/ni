import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { PunchWord } from "../components/Text";
import { COLORS, FONT } from "../theme";

// Four power pillars punch in one at a time, slow and deliberate.
export const Pillars: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [162, 180], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const subtitleOpacity = interpolate(frame, [130, 144], [0, 1], {
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
          alignItems: "center",
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        <PunchWord delay={10} color={COLORS.blue}>
          Voice.
        </PunchWord>
        <PunchWord delay={38} color={COLORS.cyan}>
          Vision.
        </PunchWord>
        <PunchWord delay={66} color={COLORS.green}>
          Memory.
        </PunchWord>
        <PunchWord delay={96} color={COLORS.amber}>
          Autonomy.
        </PunchWord>
      </div>

      <div
        style={{
          fontFamily: FONT,
          fontSize: 32,
          fontWeight: 500,
          color: COLORS.inkDim,
          letterSpacing: 6,
          textTransform: "uppercase",
          marginTop: 28,
          opacity: subtitleOpacity,
        }}
      >
        The four pillars of APEX
      </div>
    </AbsoluteFill>
  );
};
