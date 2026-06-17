import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { TerminalMock, TerminalLine } from "../components/TerminalMock";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

const GREEN = "#3ddc97";
const CYAN = "#5fd8ff";
const AMBER = "#ffb547";

const LINES: TerminalLine[] = [
  { text: `[${AMBER}][3:47 AM][/${AMBER}] APEX CORTEX — AUTONOMOUS MODE`, color: AMBER, delay: 62 },
  { text: "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color: "rgba(125,184,255,0.2)", delay: 65 },
  { text: "", delay: 66 },
  { text: "[✓]  Checked daily goals list", color: GREEN, delay: 80 },
  { text: "[✓]  Drafted morning briefing for Alex", color: GREEN, delay: 98 },
  { text: "[✓]  Summarized 47 unread emails", color: GREEN, delay: 116 },
  { text: "[→]  Running: compile weekly report...", color: CYAN, delay: 134 },
  { text: "[✓]  Report complete. Saved to vault.", color: GREEN, delay: 158 },
  { text: "[→]  Pushing notification to your phone...", color: CYAN, delay: 172 },
  { text: "[✓]  Done.", color: GREEN, delay: 192 },
  { text: "", delay: 196 },
  { text: "7 tasks completed.  0 requests made.", color: COLORS.blue, delay: 200 },
];

export const AutoCortex: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [220, 240], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bottomOpacity = interpolate(frame, [210, 222], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: sceneOut,
        flexDirection: "column",
        gap: 0,
      }}
    >
      {/* Top headline */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          marginBottom: 36,
        }}
      >
        <Title delay={6} size={52} color={COLORS.inkDim} weight={500}>
          3:47 AM — you were asleep.
        </Title>
        <Title delay={22} size={88} color={COLORS.ink} weight={900}>
          APEX was not.
        </Title>
      </div>

      <TerminalMock
        title="APEX CORTEX — AUTONOMOUS MODE"
        lines={LINES}
        width={960}
        delay={48}
      />

      {/* Bottom emphasis */}
      <div
        style={{
          marginTop: 36,
          fontFamily: FONT,
          fontSize: 32,
          fontWeight: 700,
          letterSpacing: 4,
          color: COLORS.blue,
          textTransform: "uppercase",
          opacity: bottomOpacity,
          textShadow: `0 0 30px ${COLORS.blue}66`,
        }}
      >
        No prompt required.
      </div>
    </AbsoluteFill>
  );
};
