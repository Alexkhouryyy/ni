import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";
const INDIGO = '#6366f1';

export const Scene02_Shift: React.FC = () => {
  // Local frame: 0 = global 150
  // Beat: frames 0–15 (pure black)
  // Orb blooms: frames 15–45 (local)
  // "Study Mode." slides up: frames 45–90 (local)
  // Subtitle fades: frames 90–120 (local)
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Indigo glow orb — spring scale 0→1, starts at local frame 15
  const orbScale = spring({
    frame: frame - 15,
    fps,
    config: { damping: 18, stiffness: 60 },
  });

  // Orb opacity fades in with scale
  const orbOpacity = interpolate(frame, [15, 35], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // "Study Mode." slide up — starts at local frame 45
  const titleProgress = spring({
    frame: frame - 45,
    fps,
    config: { damping: 18, stiffness: 60 },
  });
  const titleOpacity = interpolate(frame, [45, 70], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const titleY = interpolate(titleProgress, [0, 1], [40, 0]);

  // Subtitle fade — starts at local frame 90
  const subtitleOpacity = interpolate(frame, [90, 120], [0, 1], {
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
        gap: '32px',
      }}
    >
      {/* Indigo glow orb */}
      <div
        style={{
          position: 'absolute',
          width: '320px',
          height: '320px',
          borderRadius: '50%',
          backgroundColor: 'transparent',
          boxShadow: `0 0 120px 60px rgba(99,102,241,0.35), 0 0 40px 20px rgba(99,102,241,0.5)`,
          transform: `scale(${orbScale})`,
          opacity: orbOpacity,
          top: '50%',
          left: '50%',
          marginTop: '-160px',
          marginLeft: '-160px',
        }}
      />

      {/* "Study Mode." */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          fontFamily: FONT_FAMILY,
          fontSize: '140px',
          fontWeight: 800,
          color: INDIGO,
          textAlign: 'center',
          letterSpacing: '-3px',
          lineHeight: 1.0,
          position: 'relative',
          zIndex: 1,
        }}
      >
        Study Mode.
      </div>

      {/* Subtitle */}
      <div
        style={{
          opacity: subtitleOpacity,
          fontFamily: FONT_FAMILY,
          fontSize: '36px',
          fontWeight: 400,
          color: 'rgba(255,255,255,0.55)',
          textAlign: 'center',
          letterSpacing: '0px',
          lineHeight: 1.4,
          position: 'relative',
          zIndex: 1,
        }}
      >
        He&apos;ll make you work for it.
      </div>
    </AbsoluteFill>
  );
};
