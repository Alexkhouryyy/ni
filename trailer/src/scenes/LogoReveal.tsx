import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Logo } from "../components/Logo";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const LogoReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [78, 90], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const wordmarkLetter = interpolate(frame, [30, 50], [18, 8], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{ justifyContent: "center", alignItems: "center", opacity: out }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 8,
        }}
      >
        <Logo delay={0} size={300} glow={1.1} />
        <div
          style={{
            fontFamily: FONT,
            fontSize: 130,
            fontWeight: 900,
            color: COLORS.ink,
            letterSpacing: wordmarkLetter,
            marginTop: 8,
            opacity: interpolate(frame, [28, 44], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          APEX
        </div>
        <div style={{ marginTop: 4 }}>
          <Title delay={48} size={40} color={COLORS.blue} weight={600} letterSpacing={6}>
            YOUR AUTONOMOUS MIND
          </Title>
        </div>
      </div>
    </AbsoluteFill>
  );
};
