import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Logo } from "../components/Logo";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const LogoReveal: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [162, 180], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // APEX wordmark: letter-spacing collapses as it settles
  const wordmarkSpacing = interpolate(frame, [34, 58], [24, 6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const wordmarkOpacity = interpolate(frame, [30, 48], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Subtle scale breathe on the whole composition
  const breathe = 1 + 0.006 * Math.sin((frame / 30) * 1.8);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: sceneOut,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 4,
          transform: `scale(${breathe})`,
        }}
      >
        <Logo delay={0} size={320} glow={1.3} />

        <div
          style={{
            fontFamily: FONT,
            fontSize: 136,
            fontWeight: 900,
            color: COLORS.ink,
            letterSpacing: wordmarkSpacing,
            marginTop: 2,
            opacity: wordmarkOpacity,
            textShadow: `0 0 80px rgba(125,184,255,0.4)`,
          }}
        >
          APEX
        </div>

        <div style={{ marginTop: 8 }}>
          <Title
            delay={58}
            size={42}
            color={COLORS.blue}
            weight={600}
            letterSpacing={8}
          >
            YOUR AUTONOMOUS MIND
          </Title>
        </div>

        <div style={{ marginTop: 14 }}>
          <Title
            delay={88}
            size={28}
            color={COLORS.inkDim}
            weight={500}
            letterSpacing={4}
          >
            Intelligent · Relentless · Yours
          </Title>
        </div>
      </div>
    </AbsoluteFill>
  );
};
