import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";

export const Scene01_Problem: React.FC = () => {
  // useCurrentFrame() is local (0-based) inside the Sequence
  const frame = useCurrentFrame();

  // "Knowing the answer" — fades in frames 0–60
  const line1Opacity = interpolate(frame, [0, 60], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // "isn't the same as" — fades in frames 60–100
  const line2Opacity = interpolate(frame, [60, 100], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // "understanding it." — fades in frames 100–150
  const line3Opacity = interpolate(frame, [100, 150], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000000',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '24px',
      }}
    >
      <div
        style={{
          opacity: line1Opacity,
          fontFamily: FONT_FAMILY,
          fontSize: '120px',
          fontWeight: 700,
          color: '#ffffff',
          textAlign: 'center',
          letterSpacing: '-2px',
          lineHeight: 1.05,
        }}
      >
        Knowing the answer
      </div>

      <div
        style={{
          opacity: line2Opacity,
          fontFamily: FONT_FAMILY,
          fontSize: '80px',
          fontWeight: 400,
          color: 'rgba(255,255,255,0.5)',
          textAlign: 'center',
          letterSpacing: '-1px',
          lineHeight: 1.1,
        }}
      >
        isn&apos;t the same as
      </div>

      <div
        style={{
          opacity: line3Opacity,
          fontFamily: FONT_FAMILY,
          fontSize: '120px',
          fontWeight: 700,
          color: '#ffffff',
          textAlign: 'center',
          letterSpacing: '-2px',
          lineHeight: 1.05,
        }}
      >
        understanding it.
      </div>
    </AbsoluteFill>
  );
};
