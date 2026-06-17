import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

const CAPS = [
  {
    glyph: "⚡",
    title: "Autonomous Cortex",
    sub: "Works toward your goals while you sleep",
    accent: COLORS.amber,
  },
  {
    glyph: "🧠",
    title: "Total Recall",
    sub: "Remembers every word, file, and moment",
    accent: COLORS.cyan,
  },
  {
    glyph: "🛠",
    title: "Skill Forge",
    sub: "Writes and registers its own tools",
    accent: COLORS.green,
  },
  {
    glyph: "🕸",
    title: "Second Brain",
    sub: "Your knowledge, live and searchable",
    accent: COLORS.purple,
  },
  {
    glyph: "📱",
    title: "Phone Alerts",
    sub: "Push notifications straight to your pocket",
    accent: COLORS.pink,
  },
  {
    glyph: "☁️",
    title: "Always On",
    sub: "Laptop, phone, cloud — everywhere",
    accent: COLORS.blue,
  },
];

const GridCard: React.FC<{
  glyph: string;
  title: string;
  sub: string;
  accent: string;
  delay: number;
}> = ({ glyph, title, sub, accent, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 100, mass: 0.8 },
  });
  const y = interpolate(s, [0, 1], [50, 0]);
  const opacity = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        flex: "0 0 calc(33.33% - 18px)",
        opacity,
        transform: `translateY(${y}px)`,
        background: `linear-gradient(150deg, ${accent}0f, ${accent}06)`,
        border: `1px solid ${accent}30`,
        borderRadius: 22,
        padding: "28px 28px 26px",
        display: "flex",
        alignItems: "flex-start",
        gap: 22,
        boxShadow: `0 0 40px ${accent}18`,
      }}
    >
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 18,
          background: `${accent}18`,
          border: `1px solid ${accent}40`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 34,
          flexShrink: 0,
          boxShadow: `0 0 20px ${accent}22`,
        }}
      >
        {glyph}
      </div>
      <div>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 30,
            fontWeight: 800,
            color: COLORS.ink,
            letterSpacing: -0.5,
            marginBottom: 6,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: FONT,
            fontSize: 20,
            fontWeight: 500,
            color: COLORS.inkDim,
            lineHeight: 1.35,
          }}
        >
          {sub}
        </div>
      </div>
    </div>
  );
};

export const CapGrid: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [250, 270], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const STAGGER = 28;
  const GRID_START = 30;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: sceneOut,
        flexDirection: "column",
        gap: 0,
        paddingLeft: 80,
        paddingRight: 80,
      }}
    >
      <div style={{ marginBottom: 44, textAlign: "center" }}>
        <Title delay={6} size={80} color={COLORS.ink} weight={900}>
          Everything you need. Built in.
        </Title>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 24,
          width: "100%",
          maxWidth: 1680,
        }}
      >
        {CAPS.map((c, i) => (
          <GridCard
            key={i}
            {...c}
            delay={GRID_START + i * STAGGER}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
