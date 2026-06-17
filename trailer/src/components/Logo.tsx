import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme";

// The Apex mark: two stacked ascending chevrons with a blue->purple gradient.
export const Logo: React.FC<{
  delay?: number;
  size?: number;
  glow?: number;
}> = ({ delay = 0, size = 260, glow = 1 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({
    frame: frame - delay,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
  });

  // Each chevron draws/settles slightly offset for a "stacking" feel.
  const topY = interpolate(enter, [0, 1], [-40, 0]);
  const bottomY = interpolate(enter, [0, 1], [40, 0]);
  const opacity = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  const scale = interpolate(enter, [0, 1], [0.6, 1]);

  // Gentle continuous breathing glow.
  const pulse = 0.7 + 0.3 * Math.sin((frame / fps) * 2.2);

  const stroke = 34;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 240 240"
      style={{
        opacity,
        transform: `scale(${scale})`,
        filter: `drop-shadow(0 0 ${26 * glow * pulse}px rgba(125,184,255,0.65)) drop-shadow(0 0 ${
          60 * glow * pulse
        }px rgba(138,124,255,0.35))`,
      }}
    >
      <defs>
        <linearGradient id="apexgrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={COLORS.blueLight} />
          <stop offset="55%" stopColor={COLORS.blue} />
          <stop offset="100%" stopColor={COLORS.purple} />
        </linearGradient>
      </defs>
      {/* Top chevron */}
      <polyline
        points="48,118 120,52 192,118"
        fill="none"
        stroke="url(#apexgrad)"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        transform={`translate(0 ${topY})`}
      />
      {/* Bottom chevron */}
      <polyline
        points="48,180 120,114 192,180"
        fill="none"
        stroke="url(#apexgrad)"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        transform={`translate(0 ${bottomY})`}
      />
    </svg>
  );
};
