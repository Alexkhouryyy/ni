import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { NoteCard } from "../components/NoteCard";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

const NOTES = [
  {
    title: "Meeting Notes · June 17",
    preview: "Q3 roadmap finalized. Deploy Apex to Oracle by EOM...",
    tag: "work",
    accent: COLORS.blue,
    x: 80,
    y: 140,
    rotate: -1.8,
    delay: 38,
  },
  {
    title: "Project: Apex Deployment",
    preview: "Oracle VM setup complete. Tailscale HTTPS tunnel active...",
    tag: "project",
    accent: COLORS.purple,
    x: 560,
    y: 90,
    rotate: 0.8,
    delay: 56,
  },
  {
    title: "Research: LLM Architecture",
    preview: "Key findings on attention mechanisms and KV-cache efficiency...",
    tag: "research",
    accent: COLORS.cyan,
    x: 1050,
    y: 160,
    rotate: 1.5,
    delay: 74,
  },
  {
    title: "People: Alex's Team",
    preview: "Sarah — Product Lead · James — Eng · Maria — Design...",
    tag: "people",
    accent: COLORS.amber,
    x: 130,
    y: 600,
    rotate: -0.9,
    delay: 92,
  },
  {
    title: "Budget: Q3 Analysis",
    preview: "$24k runway projected. 3.2x ROI on current tooling...",
    tag: "finance",
    accent: COLORS.green,
    x: 700,
    y: 640,
    rotate: 1.2,
    delay: 110,
  },
  {
    title: "Ideas: Voice Shortcuts",
    preview: "Trigger Apex with a wake word. Persistent listener process...",
    tag: "ideas",
    accent: COLORS.pink,
    x: 1300,
    y: 580,
    rotate: -1.4,
    delay: 128,
  },
];

export const SecondBrain: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [162, 180], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bottomOpacity = interpolate(frame, [148, 160], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity: sceneOut }}>
      {/* Centered headline */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 60,
          zIndex: 10,
        }}
      >
        <Title delay={6} size={88} color={COLORS.ink} weight={900}>
          Second Brain
        </Title>
        <Title delay={20} size={40} color={COLORS.inkDim} weight={500}>
          Every thought. Every meeting. Every idea.
        </Title>
      </div>

      {/* Floating note cards */}
      {NOTES.map((n, i) => (
        <NoteCard key={i} {...n} />
      ))}

      {/* Bottom tagline */}
      <div
        style={{
          position: "absolute",
          bottom: 68,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: bottomOpacity,
        }}
      >
        <div
          style={{
            fontFamily: FONT,
            fontSize: 34,
            fontWeight: 700,
            letterSpacing: 3,
            color: COLORS.blue,
            textTransform: "uppercase",
            textShadow: `0 0 40px ${COLORS.blue}55`,
          }}
        >
          Everything connected. Always searchable.
        </div>
      </div>
    </AbsoluteFill>
  );
};
