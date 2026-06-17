import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../theme";

// A single capability: glyph + headline + sub. Slides up and settles.
export const FeatureCard: React.FC<{
  glyph: string;
  title: string;
  sub: string;
  accent: string;
  delay?: number;
}> = ({ glyph, title, sub, accent, delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 16, mass: 0.7, stiffness: 110 },
  });
  const y = interpolate(s, [0, 1], [60, 0]);
  const o = interpolate(frame - delay, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 36,
        transform: `translateY(${y}px)`,
        opacity: o,
      }}
    >
      <div
        style={{
          width: 132,
          height: 132,
          borderRadius: 30,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 64,
          background: `linear-gradient(160deg, ${accent}22, ${accent}08)`,
          border: `2px solid ${accent}55`,
          boxShadow: `0 0 40px ${accent}33`,
        }}
      >
        {glyph}
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 58,
            fontWeight: 800,
            color: COLORS.ink,
            letterSpacing: -1,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 32,
            fontWeight: 500,
            color: COLORS.inkDim,
            marginTop: 6,
          }}
        >
          {sub}
        </div>
      </div>
    </div>
  );
};
