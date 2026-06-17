import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Logo } from "../components/Logo";
import { COLORS, FONT } from "../theme";

export const CloseLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [70, 88], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeIn * fadeOut,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
        <Logo delay={2} size={210} glow={1.2} />
        <div
          style={{
            fontFamily: FONT,
            fontSize: 120,
            fontWeight: 900,
            color: COLORS.ink,
            letterSpacing: 6,
          }}
        >
          APEX
        </div>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 44,
            fontWeight: 700,
            letterSpacing: 14,
            background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.purple})`,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            opacity: interpolate(frame, [24, 40], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          ASCEND.
        </div>
      </div>
    </AbsoluteFill>
  );
};
