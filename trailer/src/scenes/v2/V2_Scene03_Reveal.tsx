import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const V2_Scene03_Reveal: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Indigo radial bloom from center — starts immediately
  const bloomScale = interpolate(frame, [0, 90], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bloomOpacity = interpolate(frame, [0, 60], [0, 0.6], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Orb at local frame 30
  const orbSpring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 80 } });
  const orbScale = interpolate(orbSpring, [0, 1], [0.3, 1]);
  const orbOpacity = interpolate(frame, [30, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "STUDY MODE." at local frame 90
  const titleSpring = spring({ frame: frame - 90, fps, config: { damping: 18, stiffness: 100 } });
  const titleY = interpolate(titleSpring, [0, 1], [60, 0]);
  const titleOpacity = interpolate(frame, [90, 115], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Underline draws at local frame 180
  const underlineWidth = interpolate(frame, [180, 230], [0, 560], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Subtitle at local frame 210
  const subtitleOpacity = interpolate(frame, [210, 240], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Fade out at end
  const sceneOpacity = interpolate(frame, [240, 265], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      {/* Radial bloom background */}
      <div style={{
        position: 'absolute',
        width: 800,
        height: 800,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(99,102,241,0.25) 0%, rgba(49,46,129,0.1) 50%, transparent 80%)',
        transform: `scale(${bloomScale})`,
        opacity: bloomOpacity,
        top: '50%',
        left: '50%',
        marginTop: -400,
        marginLeft: -400,
      }} />

      {/* JARVIS orb */}
      <div style={{
        width: 300,
        height: 300,
        borderRadius: '50%',
        background: 'radial-gradient(circle, #818cf8 0%, #6366f1 30%, #312e81 65%, transparent 100%)',
        boxShadow: '0 0 80px 30px rgba(99,102,241,0.5), 0 0 160px 60px rgba(99,102,241,0.2)',
        transform: `scale(${orbScale})`,
        opacity: orbOpacity,
        marginBottom: 48,
      }} />

      {/* STUDY MODE title */}
      <div style={{
        opacity: titleOpacity,
        transform: `translateY(${titleY}px)`,
        fontSize: 120,
        color: '#6366f1',
        fontWeight: 700,
        letterSpacing: '0.2em',
        textTransform: 'uppercase',
      }}>
        STUDY MODE.
      </div>

      {/* Indigo underline */}
      <div style={{
        width: underlineWidth,
        height: 3,
        background: 'linear-gradient(90deg, #6366f1, #a5b4fc)',
        marginTop: 8,
        marginBottom: 24,
        borderRadius: 2,
      }} />

      {/* Subtitle */}
      <div style={{
        opacity: subtitleOpacity,
        fontSize: 32,
        color: '#a5b4fc',
        fontWeight: 300,
        letterSpacing: '0.02em',
      }}>
        A different kind of intelligence.
      </div>
    </div>
  );
};
