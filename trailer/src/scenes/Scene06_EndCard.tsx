import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";
const INDIGO = '#6366f1';

// Local frame: 0 = global 570
// All elements fade in over 30 frames
// Wordmark first, then line + "Study Mode" slightly after

export const Scene06_EndCard: React.FC = () => {
  const frame = useCurrentFrame();

  // "JARVIS" wordmark fades in: local frames 0–20
  const wordmarkOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Indigo line fades in: local frames 8–24
  const lineOpacity = interpolate(frame, [8, 24], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // "Study Mode" fades in: local frames 14–30
  const subtitleOpacity = interpolate(frame, [14, 30], [0, 1], {
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
        gap: '16px',
      }}
    >
      {/* JARVIS wordmark */}
      <div
        style={{
          opacity: wordmarkOpacity,
          fontFamily: FONT_FAMILY,
          fontSize: '80px',
          fontWeight: 700,
          color: '#ffffff',
          textAlign: 'center',
          letterSpacing: '-2px',
          lineHeight: 1.0,
        }}
      >
        JARVIS
      </div>

      {/* Thin indigo divider line */}
      <div
        style={{
          opacity: lineOpacity,
          width: '200px',
          height: '2px',
          backgroundColor: INDIGO,
          borderRadius: '1px',
        }}
      />

      {/* "Study Mode" subtitle */}
      <div
        style={{
          opacity: subtitleOpacity,
          fontFamily: FONT_FAMILY,
          fontSize: '32px',
          fontWeight: 400,
          color: INDIGO,
          textAlign: 'center',
          letterSpacing: '2px',
          lineHeight: 1.4,
        }}
      >
        Study Mode
      </div>
    </AbsoluteFill>
  );
};
