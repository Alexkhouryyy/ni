import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

const SummaryLine: React.FC<{
  text: string;
  color: string;
  opacity: number;
  translateY: number;
}> = ({ text, color, opacity, translateY }) => (
  <div style={{
    opacity,
    transform: `translateY(${translateY}px)`,
    fontSize: 18,
    color,
    fontWeight: 400,
    lineHeight: 1.6,
    padding: '4px 0',
  }}>
    {text}
  </div>
);

export const V2_Scene08_Summary: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [265, 295], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 265 ? sceneIn : sceneOut;

  // Toggle animation — local frame 30 (global 2130)
  // Toggle goes from indigo (on) to grey (off)
  const toggleProgress = interpolate(frame, [30, 75], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const toggleX = interpolate(toggleProgress, [0, 1], [0, 28]);
  const toggleBg = interpolate(toggleProgress, [0, 1], [99, 55]); // hue for indigo → grey
  const toggleBgColor = `hsl(${toggleBg}, ${interpolate(toggleProgress, [0, 1], [70, 5])}%, ${interpolate(toggleProgress, [0, 1], [55, 40])}%)`;

  // Summary card appears at local frame 90 (global 2190)
  const cardSpring = spring({ frame: frame - 90, fps, config: { damping: 22, stiffness: 80 } });
  const cardY = interpolate(cardSpring, [0, 1], [40, 0]);
  const cardOpacity = interpolate(frame, [90, 120], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Staggered line appearances — local frames 210, 230, 250 (global 2310, 2330, 2350)
  const line1Spring = spring({ frame: frame - 210, fps, config: { damping: 22, stiffness: 90 } });
  const line1Y = interpolate(line1Spring, [0, 1], [16, 0]);
  const line1Opacity = interpolate(frame, [210, 230], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const line2Spring = spring({ frame: frame - 230, fps, config: { damping: 22, stiffness: 90 } });
  const line2Y = interpolate(line2Spring, [0, 1], [16, 0]);
  const line2Opacity = interpolate(frame, [230, 250], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const line3Spring = spring({ frame: frame - 250, fps, config: { damping: 22, stiffness: 90 } });
  const line3Y = interpolate(line3Spring, [0, 1], [16, 0]);
  const line3Opacity = interpolate(frame, [250, 270], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Progress. Tracked." at local frame 270 (global 2370)
  const progressSpring = spring({ frame: frame - 270, fps, config: { damping: 18, stiffness: 100 } });
  const progressY = interpolate(progressSpring, [0, 1], [20, 0]);
  const progressOpacity = interpolate(frame, [270, 290], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: '#000000',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      opacity: sceneOpacity,
      gap: 40,
    }}>
      {/* Toggle UI */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        marginBottom: 8,
      }}>
        <span style={{ fontSize: 16, color: '#9ca3af', fontWeight: 500 }}>Study Mode</span>
        {/* Toggle track */}
        <div style={{
          width: 56,
          height: 28,
          borderRadius: 14,
          background: toggleBgColor,
          position: 'relative',
          border: '1px solid rgba(255,255,255,0.1)',
        }}>
          {/* Toggle thumb */}
          <div style={{
            position: 'absolute',
            top: 3,
            left: 3 + toggleX,
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: '#ffffff',
            boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
          }} />
        </div>
        <span style={{
          fontSize: 14,
          color: interpolate(toggleProgress, [0, 1], [0.9, 0.4]) > 0.6 ? '#6366f1' : '#6b7280',
          fontWeight: 500,
        }}>
          {toggleProgress < 0.5 ? 'ON' : 'OFF'}
        </span>
      </div>

      {/* Summary card */}
      <div style={{
        opacity: cardOpacity,
        transform: `translateY(${cardY}px)`,
        background: '#0a0a12',
        border: '1px solid #1f1f35',
        borderTop: '3px solid #6366f1',
        borderRadius: 12,
        padding: '28px 36px',
        width: 760,
      }}>
        {/* Title */}
        <div style={{
          fontSize: 20,
          color: '#6366f1',
          fontWeight: 600,
          letterSpacing: '0.03em',
          marginBottom: 20,
        }}>
          Session Summary
        </div>

        <SummaryLine
          text="Topics covered: Recursion, Base cases, Stack frames"
          color="#ffffff"
          opacity={line1Opacity}
          translateY={line1Y}
        />
        <SummaryLine
          text="Strongest: Conceptual understanding ✓"
          color="#4ade80"
          opacity={line2Opacity}
          translateY={line2Y}
        />
        <SummaryLine
          text="Review: Stack overflow edge cases"
          color="#fbbf24"
          opacity={line3Opacity}
          translateY={line3Y}
        />
      </div>

      {/* "Progress. Tracked." */}
      <div style={{
        opacity: progressOpacity,
        transform: `translateY(${progressY}px)`,
        fontSize: 32,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.01em',
      }}>
        Progress. Tracked.
      </div>
    </div>
  );
};
