import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';
import { MODES } from './modeColors';

export const MS_Outro: React.FC = () => {
  const frame = useCurrentFrame();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [330, 360], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 330 ? sceneIn : sceneOut;

  // "JARVIS." — first
  const line1Opacity = interpolate(frame, [20, 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1Y = interpolate(frame, [20, 50], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Six personalities." — second
  const line2Opacity = interpolate(frame, [80, 110], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2Y = interpolate(frame, [80, 110], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "One intelligence." — third
  const line3Opacity = interpolate(frame, [140, 170], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line3Y = interpolate(frame, [140, 170], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Choose wisely." — fourth
  const line4Opacity = interpolate(frame, [200, 230], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Color dots
  const dotsOpacity = interpolate(frame, [90, 130], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#000000',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      opacity: sceneOpacity,
      gap: 4,
    }}>
      {/* JARVIS. */}
      <div style={{
        opacity: line1Opacity,
        transform: `translateY(${line1Y}px)`,
        fontSize: 96,
        fontWeight: 800,
        color: '#ffffff',
        letterSpacing: '-0.04em',
      }}>
        JARVIS.
      </div>

      {/* Color dots row */}
      <div style={{
        display: 'flex', gap: 10, opacity: dotsOpacity, marginTop: 4, marginBottom: 4,
      }}>
        {MODES.map(m => (
          <div key={m.id} style={{
            width: 10, height: 10, borderRadius: '50%',
            background: m.color,
            boxShadow: `0 0 10px ${m.color}`,
          }} />
        ))}
      </div>

      {/* Six personalities. */}
      <div style={{
        opacity: line2Opacity,
        transform: `translateY(${line2Y}px)`,
        fontSize: 40,
        fontWeight: 300,
        color: '#9ca3af',
        letterSpacing: '-0.01em',
        marginTop: 8,
      }}>
        Six personalities.
      </div>

      {/* One intelligence. */}
      <div style={{
        opacity: line3Opacity,
        transform: `translateY(${line3Y}px)`,
        fontSize: 40,
        fontWeight: 300,
        color: '#9ca3af',
        letterSpacing: '-0.01em',
      }}>
        One intelligence.
      </div>

      {/* Choose wisely. */}
      <div style={{
        opacity: line4Opacity,
        fontSize: 20,
        color: '#374151',
        fontStyle: 'italic',
        fontWeight: 300,
        letterSpacing: '0.04em',
        marginTop: 32,
      }}>
        Choose wisely.
      </div>
    </div>
  );
};
