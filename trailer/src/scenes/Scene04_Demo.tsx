import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";
const INDIGO = '#6366f1';

// Local frame: 0 = global 390
// Question appears: local frames 0–30
// Pause: local frames 30–60
// JARVIS response appears: local frames 60–90

export const Scene04_Demo: React.FC = () => {
  const frame = useCurrentFrame();

  // Question fades in frames 0–30
  const questionOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Response fades in frames 60–90
  const responseOpacity = interpolate(frame, [60, 90], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000000',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '0 240px',
        gap: '48px',
      }}
    >
      {/* User question — left aligned */}
      <div
        style={{
          opacity: questionOpacity,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: '10px',
        }}
      >
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: '22px',
            fontWeight: 400,
            color: 'rgba(255,255,255,0.35)',
            letterSpacing: '1px',
            textTransform: 'uppercase',
          }}
        >
          You
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: '48px',
            fontWeight: 500,
            color: '#ffffff',
            letterSpacing: '-0.5px',
            lineHeight: 1.2,
          }}
        >
          What is recursion?
        </div>
      </div>

      {/* JARVIS response — right aligned */}
      <div
        style={{
          opacity: responseOpacity,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: '10px',
        }}
      >
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: '22px',
            fontWeight: 400,
            color: 'rgba(99,102,241,0.5)',
            letterSpacing: '1px',
            textTransform: 'uppercase',
          }}
        >
          JARVIS
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: '48px',
            fontWeight: 600,
            color: INDIGO,
            letterSpacing: '-0.5px',
            lineHeight: 1.2,
            textAlign: 'right',
          }}
        >
          What do YOU think it means?
        </div>
      </div>
    </AbsoluteFill>
  );
};
