import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Logo } from "../components/Logo";
import { COLORS, FONT } from "../theme";

export const CloseLogo: React.FC = () => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [218, 240], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // APEX wordmark: letter-spacing collapses on settle
  const wordmarkSpacing = interpolate(frame, [28, 52], [20, 6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const wordmarkOpacity = interpolate(frame, [24, 42], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // "ASCEND." gradient text
  const ascendOpacity = interpolate(frame, [54, 74], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ascendY = interpolate(frame, [54, 72], [22, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Final tagline
  const taglineOpacity = interpolate(frame, [100, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Gentle scale breathe on the whole composition
  const breathe = 1 + 0.007 * Math.sin((frame / 30) * 1.6);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeIn * fadeOut,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 10,
          transform: `scale(${breathe})`,
        }}
      >
        <Logo delay={2} size={260} glow={1.5} />

        <div
          style={{
            fontFamily: FONT,
            fontSize: 136,
            fontWeight: 900,
            color: COLORS.ink,
            letterSpacing: wordmarkSpacing,
            opacity: wordmarkOpacity,
            textShadow: `0 0 80px rgba(125,184,255,0.45), 0 0 160px rgba(138,124,255,0.25)`,
          }}
        >
          APEX
        </div>

        <div
          style={{
            fontFamily: FONT,
            fontSize: 56,
            fontWeight: 800,
            letterSpacing: 18,
            background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.purple}, ${COLORS.pink})`,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            opacity: ascendOpacity,
            transform: `translateY(${ascendY}px)`,
            textShadow: "none",
          }}
        >
          ASCEND.
        </div>

        <div
          style={{
            fontFamily: FONT,
            fontSize: 28,
            fontWeight: 500,
            color: COLORS.inkDim,
            letterSpacing: 3,
            marginTop: 8,
            opacity: taglineOpacity,
          }}
        >
          The last AI you&apos;ll ever need.
        </div>
      </div>
    </AbsoluteFill>
  );
};
