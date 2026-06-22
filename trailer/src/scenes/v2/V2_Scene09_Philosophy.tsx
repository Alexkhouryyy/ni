import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';

export const V2_Scene09_Philosophy: React.FC = () => {
  const frame = useCurrentFrame();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [175, 205], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 175 ? sceneIn : sceneOut;

  // "Knowing the answer" at local frame 30 (global 2430)
  const line1Opacity = interpolate(frame, [30, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1Y = interpolate(frame, [30, 60], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "isn't the same as" at local frame 90 (global 2490)
  const line2Opacity = interpolate(frame, [90, 115], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2Y = interpolate(frame, [90, 115], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "understanding it." at local frame 150 (global 2550)
  const line3Opacity = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line3Y = interpolate(frame, [150, 175], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      gap: 8,
    }}>
      <div style={{
        opacity: line1Opacity,
        transform: `translateY(${line1Y}px)`,
        fontSize: 80,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.03em',
        lineHeight: 1.1,
      }}>
        Knowing the answer
      </div>

      <div style={{
        opacity: line2Opacity,
        transform: `translateY(${line2Y}px)`,
        fontSize: 64,
        color: '#6b7280',
        fontWeight: 300,
        letterSpacing: '-0.02em',
        lineHeight: 1.15,
      }}>
        isn't the same as
      </div>

      <div style={{
        opacity: line3Opacity,
        transform: `translateY(${line3Y}px)`,
        fontSize: 80,
        color: '#ffffff',
        fontWeight: 700,
        letterSpacing: '-0.03em',
        lineHeight: 1.1,
      }}>
        understanding it.
      </div>
    </div>
  );
};
