import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';

export const MS_Intro: React.FC = () => {
  const frame = useCurrentFrame();

  // "Six modes." — slides up and fades in
  const line1Opacity = interpolate(frame, [20, 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1Y = interpolate(frame, [20, 50], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1Out = interpolate(frame, [210, 250], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "One JARVIS." — after line1
  const line2Opacity = interpolate(frame, [80, 110], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2Y = interpolate(frame, [80, 110], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2Out = interpolate(frame, [210, 250], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Six personalities." — smaller subline
  const line3Opacity = interpolate(frame, [140, 170], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line3Out = interpolate(frame, [210, 250], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Six colored dots representing each mode — appear one by one
  const dotColors = ['#f59e0b', '#ef4444', '#22c55e', '#8b5cf6', '#0ea5e9', '#f43f5e'];
  const dotOpacities = dotColors.map((_, i) =>
    interpolate(frame, [160 + i * 8, 175 + i * 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  );
  const dotsOut = interpolate(frame, [210, 250], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Scene out
  const sceneOpacity = interpolate(frame, [250, 270], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
    }}>
      {/* "Six modes." */}
      <div style={{
        opacity: frame < 210 ? line1Opacity : line1Out,
        transform: `translateY(${line1Y}px)`,
        fontSize: 96,
        fontWeight: 800,
        color: '#ffffff',
        letterSpacing: '-0.03em',
        lineHeight: 1,
      }}>
        Six modes.
      </div>

      {/* "One JARVIS." */}
      <div style={{
        opacity: frame < 210 ? line2Opacity : line2Out,
        transform: `translateY(${line2Y}px)`,
        fontSize: 64,
        fontWeight: 300,
        color: '#9ca3af',
        letterSpacing: '-0.02em',
        marginTop: 16,
      }}>
        One JARVIS.
      </div>

      {/* "Six personalities." */}
      <div style={{
        opacity: frame < 210 ? line3Opacity : line3Out,
        fontSize: 22,
        color: '#4b5563',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        fontWeight: 400,
        marginTop: 40,
      }}>
        Toggle on demand.
      </div>

      {/* Six colored dots */}
      <div style={{
        display: 'flex',
        gap: 16,
        marginTop: 40,
        opacity: dotsOut,
      }}>
        {dotColors.map((c, i) => (
          <div key={i} style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: c,
            opacity: dotOpacities[i],
            boxShadow: `0 0 12px ${c}`,
          }} />
        ))}
      </div>
    </div>
  );
};
