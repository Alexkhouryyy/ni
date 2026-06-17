import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { TerminalMock, TerminalLine } from "../components/TerminalMock";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

const GREEN = "#3ddc97";
const CYAN = "#5fd8ff";
const PURPLE = "#a78bfa";
const BLUE = "#7db8ff";

const LINES: TerminalLine[] = [
  { text: "[Skill Forge]  Novel capability required", color: CYAN, delay: 62 },
  { text: "[→]  Analyzing task pattern...", color: CYAN, delay: 78 },
  { text: "[→]  Writing: fetch_flight_prices.py", color: CYAN, delay: 96 },
  { text: "", delay: 108 },
  { text: "def fetch_flight_prices(origin, dest, date):", color: PURPLE, delay: 112 },
  { text: "    # APEX Skill Forge — auto-generated", color: GREEN, delay: 118, dim: true },
  { text: "    results = api.search_flights(origin, dest, date)", color: BLUE, delay: 124 },
  { text: "    return sorted(results, key=lambda x: x['price'])", color: BLUE, delay: 130 },
  { text: "", delay: 137 },
  { text: "[OK]  Tool registered. Running tests...", color: GREEN, delay: 144 },
  { text: "[OK]  14 flights found. First run succeeded.", color: GREEN, delay: 164 },
  { text: "[OK]  Added to skill library. Available for future use.", color: GREEN, delay: 184 },
];

export const SkillForge: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [220, 240], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bottomOpacity = interpolate(frame, [205, 218], [0, 1], {
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
      <div style={{ marginBottom: 36, textAlign: "center" }}>
        <Title delay={6} size={88} color={COLORS.ink} weight={900}>
          Skill Forge
        </Title>
        <Title delay={22} size={40} color={COLORS.inkDim} weight={500}>
          When it lacks a tool, it writes one.
        </Title>
      </div>

      <TerminalMock
        title="APEX SKILL FORGE"
        lines={LINES}
        width={960}
        delay={46}
      />

      <div
        style={{
          marginTop: 34,
          fontFamily: FONT,
          fontSize: 30,
          fontWeight: 700,
          letterSpacing: 3,
          color: COLORS.green,
          textTransform: "uppercase",
          opacity: bottomOpacity,
          textShadow: `0 0 30px ${COLORS.green}55`,
        }}
      >
        12 skills auto-written this month.
      </div>
    </AbsoluteFill>
  );
};
