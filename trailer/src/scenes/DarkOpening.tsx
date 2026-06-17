import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT } from "../theme";

// Cinematic cold open — absolute darkness, then two punchy lines.
export const DarkOpening: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneFade = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sceneOut = interpolate(frame, [105, 120], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Line 1: scan-reveal left → right
  const scan1 = interpolate(frame, [14, 42], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const opacity1 = interpolate(frame, [14, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Line 2: appears after a deliberate beat
  const opacity2 = interpolate(frame, [58, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y2 = interpolate(frame, [58, 74], [28, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: sceneFade * sceneOut,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
        }}
      >
        {/* Line 1 — scan reveal */}
        <div
          style={{
            overflow: "hidden",
            opacity: opacity1,
          }}
        >
          <div
            style={{
              fontFamily: FONT,
              fontSize: 72,
              fontWeight: 600,
              color: COLORS.inkDim,
              letterSpacing: -1,
              textAlign: "center",
              clipPath: `inset(0 ${(1 - scan1) * 100}% 0 0)`,
            }}
          >
            Every AI assistant waits to be asked.
          </div>
        </div>

        {/* Line 2 — punch in from below */}
        <div
          style={{
            fontFamily: FONT,
            fontSize: 100,
            fontWeight: 900,
            color: COLORS.ink,
            letterSpacing: -3,
            textAlign: "center",
            opacity: opacity2,
            transform: `translateY(${y2}px)`,
            textShadow: `0 0 60px rgba(125,184,255,0.35)`,
          }}
        >
          This one doesn&apos;t.
        </div>
      </div>
    </AbsoluteFill>
  );
};
