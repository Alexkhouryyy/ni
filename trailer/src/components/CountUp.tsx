import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT } from "../theme";

export const CountUp: React.FC<{
  end: number;
  label: string;
  suffix?: string;
  accent?: string;
  delay?: number;
  duration?: number;
}> = ({
  end,
  label,
  suffix = "",
  accent = COLORS.blue,
  delay = 0,
  duration = 70,
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const value = Math.round(progress * end);

  const opacity = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(frame - delay, [0, 18], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        textAlign: "center",
        opacity,
        transform: `translateY(${y}px)`,
        padding: "32px 40px",
        borderRadius: 20,
        background: `linear-gradient(160deg, ${accent}0d, transparent)`,
        border: `1px solid ${accent}28`,
      }}
    >
      <div
        style={{
          fontFamily: FONT,
          fontSize: 96,
          fontWeight: 900,
          color: accent,
          letterSpacing: -4,
          lineHeight: 1,
          textShadow: `0 0 50px ${accent}88, 0 0 100px ${accent}44`,
        }}
      >
        {value.toLocaleString()}
        {suffix}
      </div>
      <div
        style={{
          fontFamily: FONT,
          fontSize: 24,
          fontWeight: 600,
          color: COLORS.inkDim,
          letterSpacing: 3,
          textTransform: "uppercase",
          marginTop: 14,
        }}
      >
        {label}
      </div>
    </div>
  );
};
