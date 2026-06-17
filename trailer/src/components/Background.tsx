import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, random } from "remotion";
import { COLORS } from "../theme";

// Deep-space background: two slow-drifting radial glows + a field of stars.
export const Background: React.FC<{ seed?: string }> = ({ seed = "apex" }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const t = frame / fps;

  const g1x = 30 + 12 * Math.sin(t * 0.35);
  const g1y = 35 + 10 * Math.cos(t * 0.27);
  const g2x = 72 + 10 * Math.cos(t * 0.31);
  const g2y = 68 + 9 * Math.sin(t * 0.4);

  const stars = new Array(70).fill(0).map((_, i) => {
    const x = random(seed + "x" + i) * width;
    const y = random(seed + "y" + i) * height;
    const baseR = 0.6 + random(seed + "r" + i) * 1.8;
    const tw = 0.4 + 0.6 * Math.sin(t * (0.8 + random(seed + "t" + i) * 1.6) + i);
    return { x, y, r: baseR, o: 0.25 + 0.55 * tw };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(40% 50% at ${g1x}% ${g1y}%, rgba(125,184,255,0.18), transparent 70%),
                       radial-gradient(38% 46% at ${g2x}% ${g2y}%, rgba(138,124,255,0.16), transparent 70%)`,
        }}
      />
      <svg width={width} height={height} style={{ position: "absolute" }}>
        {stars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#cfe0ff" opacity={s.o} />
        ))}
      </svg>
      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(70% 70% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
