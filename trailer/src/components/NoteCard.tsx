import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../theme";

export const NoteCard: React.FC<{
  title: string;
  preview: string;
  tag: string;
  accent?: string;
  delay: number;
  x: number;
  y: number;
  rotate?: number;
}> = ({ title, preview, tag, accent = COLORS.blue, delay, x, y, rotate = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 22, stiffness: 70, mass: 1.1 },
  });

  const opacity = interpolate(frame - delay, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(s, [0, 1], [0.85, 1]);

  // Gentle continuous drift
  const drift =
    Math.sin((frame + delay * 7) / 55) * 5 +
    Math.cos((frame + delay * 3) / 80) * 3;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y + drift,
        width: 400,
        opacity,
        transform: `scale(${scale}) rotate(${rotate}deg)`,
      }}
    >
      <div
        style={{
          background: "rgba(7, 11, 20, 0.92)",
          border: `1px solid ${accent}30`,
          borderRadius: 14,
          padding: "18px 22px",
          boxShadow: `0 4px 30px rgba(0,0,0,0.5), 0 0 40px ${accent}18`,
        }}
      >
        <div
          style={{
            fontFamily: FONT,
            fontSize: 20,
            fontWeight: 700,
            color: COLORS.ink,
            marginBottom: 8,
            letterSpacing: -0.3,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 16,
            color: COLORS.inkDim,
            lineHeight: 1.4,
            marginBottom: 12,
          }}
        >
          {preview}
        </div>
        <div
          style={{
            display: "inline-block",
            background: `${accent}1a`,
            border: `1px solid ${accent}40`,
            borderRadius: 6,
            padding: "3px 10px",
            fontFamily: FONT,
            fontSize: 13,
            fontWeight: 600,
            color: accent,
            letterSpacing: 1,
          }}
        >
          #{tag}
        </div>
      </div>
    </div>
  );
};
