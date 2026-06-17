import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../theme";

export const ChatBubble: React.FC<{
  role: "user" | "apex";
  text: string;
  delay: number;
}> = ({ role, text, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isApex = role === "apex";

  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 20, stiffness: 85, mass: 0.8 },
  });
  const x = interpolate(s, [0, 1], [isApex ? -50 : 50, 0]);
  const opacity = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isApex ? "flex-start" : "flex-end",
        opacity,
        transform: `translateX(${x}px)`,
        marginBottom: 20,
        width: "100%",
      }}
    >
      {isApex && (
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 14,
            marginRight: 14,
            background: `linear-gradient(135deg, ${COLORS.blue}, ${COLORS.purple})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 24,
            flexShrink: 0,
            alignSelf: "flex-end",
            marginBottom: 4,
            boxShadow: `0 0 20px ${COLORS.blue}44`,
          }}
        >
          ⚡
        </div>
      )}
      <div
        style={{
          maxWidth: 720,
          padding: "16px 24px 18px",
          borderRadius: isApex ? "6px 22px 22px 22px" : "22px 6px 22px 22px",
          background: isApex
            ? `linear-gradient(150deg, rgba(125,184,255,0.13), rgba(138,124,255,0.07))`
            : "rgba(255,255,255,0.09)",
          border: isApex
            ? `1px solid rgba(125,184,255,0.28)`
            : "1px solid rgba(255,255,255,0.12)",
          fontFamily: FONT,
          lineHeight: 1.45,
        }}
      >
        {isApex && (
          <div
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: COLORS.blue,
              letterSpacing: 2,
              marginBottom: 6,
              textTransform: "uppercase",
            }}
          >
            APEX
          </div>
        )}
        <div
          style={{
            fontSize: 28,
            fontWeight: isApex ? 500 : 400,
            color: isApex ? COLORS.blueLight : COLORS.ink,
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};
