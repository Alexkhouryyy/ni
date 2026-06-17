import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { ChatBubble } from "../components/ChatBubble";
import { Title } from "../components/Text";
import { COLORS, FONT } from "../theme";

export const VoiceVision: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneOut = interpolate(frame, [192, 210], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const chatAreaOpacity = interpolate(frame, [42, 54], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const pillsOpacity = interpolate(frame, [18, 30], [0, 1], {
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
      {/* Headline */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          marginBottom: 10,
        }}
      >
        <Title delay={6} size={88} color={COLORS.ink} weight={900}>
          Voice + Vision
        </Title>
        <Title delay={22} size={38} color={COLORS.inkDim} weight={500}>
          Sees what you see. Hears what you say.
        </Title>
      </div>

      {/* Input mode pills */}
      <div
        style={{
          display: "flex",
          gap: 16,
          marginBottom: 32,
          opacity: pillsOpacity,
        }}
      >
        {[
          { icon: "🎤", label: "Voice", color: COLORS.blue },
          { icon: "👁", label: "Vision", color: COLORS.purple },
          { icon: "⌨️", label: "Text", color: COLORS.cyan },
        ].map(({ icon, label, color }) => (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 20px",
              borderRadius: 40,
              background: `${color}18`,
              border: `1px solid ${color}40`,
              fontFamily: FONT,
              fontSize: 20,
              fontWeight: 600,
              color,
              letterSpacing: 1,
            }}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </div>
        ))}
      </div>

      {/* Chat area */}
      <div
        style={{
          width: 860,
          opacity: chatAreaOpacity,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <ChatBubble
          role="user"
          text="Find me the best flight to NYC this weekend under $200."
          delay={55}
        />
        <ChatBubble
          role="apex"
          text="Found it. Delta nonstop, $178. Departs 7:15 AM Saturday. Should I book it?"
          delay={100}
        />
        <ChatBubble role="user" text="Yes, book it." delay={150} />
        <ChatBubble
          role="apex"
          text="Done. Confirmation sent. Added to your calendar: NYC Trip — Saturday 7:15 AM."
          delay={175}
        />
      </div>
    </AbsoluteFill>
  );
};
