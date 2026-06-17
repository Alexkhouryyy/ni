import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../theme";

// Fade + rise headline.
export const Title: React.FC<{
  children: React.ReactNode;
  delay?: number;
  size?: number;
  weight?: number;
  color?: string;
  letterSpacing?: number;
}> = ({
  children,
  delay = 0,
  size = 90,
  weight = 800,
  color = COLORS.ink,
  letterSpacing = -2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 90 } });
  const y = interpolate(s, [0, 1], [40, 0]);
  const o = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: size,
        fontWeight: weight,
        color,
        letterSpacing,
        textAlign: "center",
        transform: `translateY(${y}px)`,
        opacity: o,
        lineHeight: 1.05,
      }}
    >
      {children}
    </div>
  );
};

// A word that punches in with scale, used for the pillars beat.
export const PunchWord: React.FC<{
  children: React.ReactNode;
  delay: number;
  color?: string;
}> = ({ children, delay, color = COLORS.ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 12, mass: 0.6, stiffness: 200 },
  });
  const scale = interpolate(s, [0, 1], [1.6, 1]);
  const o = interpolate(frame - delay, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        fontFamily: FONT,
        fontSize: 96,
        fontWeight: 900,
        color,
        letterSpacing: -2,
        display: "inline-block",
        transform: `scale(${scale})`,
        opacity: o,
        margin: "0 14px",
      }}
    >
      {children}
    </span>
  );
};
