import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";

// Local frame: 0 = global 480
// Beat: local frames 0–30 (pure black)
// "JARVIS." fades in: local frames 30–60
// Pause: local frames 60–75
// "The teacher you always needed." slides up: local frames 75–90

export const Scene05_Tagline: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // "JARVIS." fades in at local frame 30
  const wordmarkOpacity = interpolate(frame, [30, 60], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Tagline slides up from local frame 75
  const taglineProgress = spring({
    frame: frame - 75,
    fps,
    config: { damping: 18, stiffness: 60 },
  });

  const taglineOpacity = interpolate(frame, [75, 90], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const taglineY = interpolate(taglineProgress, [0, 1], [40, 0]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000000',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '28px',
      }}
    >
      <div
        style={{
          opacity: wordmarkOpacity,
          fontFamily: FONT_FAMILY,
          fontSize: '100px',
          fontWeight: 700,
          color: '#ffffff',
          textAlign: 'center',
          letterSpacing: '-3px',
          lineHeight: 1.0,
        }}
      >
        JARVIS.
      </div>

      <div
        style={{
          opacity: taglineOpacity,
          transform: `translateY(${taglineY}px)`,
          fontFamily: FONT_FAMILY,
          fontSize: '48px',
          fontWeight: 400,
          color: 'rgba(255,255,255,0.55)',
          textAlign: 'center',
          letterSpacing: '-0.5px',
          lineHeight: 1.3,
        }}
      >
        The teacher you always needed.
      </div>
    </AbsoluteFill>
  );
};
