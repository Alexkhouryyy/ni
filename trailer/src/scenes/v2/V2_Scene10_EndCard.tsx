import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const V2_Scene10_EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Background glow pulse
  const pulseSin = Math.sin(frame * 0.08);
  const bgGlow = interpolate(pulseSin, [-1, 1], [0.15, 0.35]);

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  // Final fade to black — last 30 frames
  const sceneOut = interpolate(frame, [60, 90], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 60 ? sceneIn : sceneOut;

  // "JARVIS." — local frame 10 (global 2620)
  const jarvisSpring = spring({ frame: frame - 10, fps, config: { damping: 18, stiffness: 120 } });
  const jarvisY = interpolate(jarvisSpring, [0, 1], [40, 0]);
  const jarvisOpacity = interpolate(frame, [10, 30], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Study Mode." — local frame 40 (global 2650)
  const studySpring = spring({ frame: frame - 40, fps, config: { damping: 20, stiffness: 100 } });
  const studyY = interpolate(studySpring, [0, 1], [24, 0]);
  const studyOpacity = interpolate(frame, [40, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Underline — local frame 60 (global 2670)
  const underlineWidth = interpolate(frame, [60, 85], [0, 380], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Tagline — local frame 70 (global 2680)
  const tagOpacity = interpolate(frame, [70, 88], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Deep indigo glow background */}
      <div style={{
        position: 'absolute',
        width: 1200,
        height: 600,
        borderRadius: '50%',
        background: `radial-gradient(ellipse, rgba(99,102,241,${bgGlow}) 0%, rgba(49,46,129,${bgGlow * 0.4}) 50%, transparent 75%)`,
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
      }} />

      {/* Content */}
      <div style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 0,
      }}>
        {/* JARVIS. */}
        <div style={{
          opacity: jarvisOpacity,
          transform: `translateY(${jarvisY}px)`,
          fontSize: 96,
          color: '#ffffff',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          lineHeight: 1.0,
        }}>
          JARVIS.
        </div>

        {/* Study Mode. */}
        <div style={{
          opacity: studyOpacity,
          transform: `translateY(${studyY}px)`,
          fontSize: 48,
          color: '#a5b4fc',
          fontWeight: 400,
          letterSpacing: '0.04em',
          marginTop: 8,
        }}>
          Study Mode.
        </div>

        {/* Indigo underline */}
        <div style={{
          width: underlineWidth,
          height: 2,
          background: 'linear-gradient(90deg, transparent, #6366f1, transparent)',
          margin: '16px 0 20px',
          borderRadius: 1,
        }} />

        {/* Tagline */}
        <div style={{
          opacity: tagOpacity,
          fontSize: 24,
          color: '#6b7280',
          fontWeight: 400,
          letterSpacing: '0.01em',
        }}>
          The teacher you always needed.
        </div>
      </div>
    </div>
  );
};
