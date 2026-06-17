import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT } from "../theme";

const MONO = "'SF Mono', 'Fira Code', 'Consolas', 'Courier New', monospace";

export interface TerminalLine {
  text: string;
  color?: string;
  delay: number;
  dim?: boolean;
}

export const TerminalMock: React.FC<{
  title?: string;
  lines: TerminalLine[];
  width?: number;
  delay?: number;
}> = ({ title = "APEX TERMINAL", lines, width = 920, delay = 0 }) => {
  const frame = useCurrentFrame();

  const slideIn = interpolate(frame - delay, [0, 18], [50, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeIn = interpolate(frame - delay, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width,
        background: "rgba(4, 8, 18, 0.94)",
        border: "1px solid rgba(125, 184, 255, 0.22)",
        borderRadius: 18,
        padding: "26px 36px 30px",
        boxShadow:
          "0 0 80px rgba(125,184,255,0.10), 0 0 200px rgba(138,124,255,0.06), 0 16px 60px rgba(0,0,0,0.7)",
        opacity: fadeIn,
        transform: `translateY(${slideIn}px)`,
      }}
    >
      {/* Title bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 18,
        }}
      >
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            background: "#ff5f57",
          }}
        />
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            background: "#febc2e",
          }}
        />
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            background: "#28c840",
          }}
        />
        <span
          style={{
            fontFamily: FONT,
            fontSize: 14,
            fontWeight: 600,
            color: COLORS.inkDim,
            marginLeft: 14,
            letterSpacing: 2,
            textTransform: "uppercase",
          }}
        >
          {title}
        </span>
      </div>
      <div
        style={{
          height: 1,
          background: "rgba(125,184,255,0.14)",
          marginBottom: 22,
        }}
      />
      <div style={{ fontFamily: MONO, fontSize: 22, lineHeight: 1.65 }}>
        {lines.map((line, i) => {
          const opacity = interpolate(
            frame,
            [line.delay, line.delay + 6],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const y = interpolate(
            frame,
            [line.delay, line.delay + 5],
            [7, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <div
              key={i}
              style={{
                color: line.color ?? (line.dim ? COLORS.inkDim : COLORS.ink),
                opacity,
                transform: `translateY(${y}px)`,
                marginBottom: line.text === "" ? 4 : 0,
              }}
            >
              {line.text}
            </div>
          );
        })}
      </div>
    </div>
  );
};
