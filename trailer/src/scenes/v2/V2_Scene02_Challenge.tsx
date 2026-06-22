import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';

export const V2_Scene02_Challenge: React.FC = () => {
  const frame = useCurrentFrame();

  // "But real learning" at local frame 30 (global 300)
  const line1Opacity = interpolate(frame, [30, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1FadeOut = interpolate(frame, [200, 220], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1Final = frame < 200 ? line1Opacity : line1FadeOut;
  const line1Y = interpolate(frame, [30, 55], [24, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "comes from the struggle." at local frame 90 (global 360)
  const line2Opacity = interpolate(frame, [90, 115], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2FadeOut = interpolate(frame, [200, 220], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2Final = frame < 200 ? line2Opacity : line2FadeOut;
  const line2Y = interpolate(frame, [90, 115], [24, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Horizontal line at local frame 150 (global 420)
  const lineOpacity = interpolate(frame, [150, 170], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const lineFadeOut = interpolate(frame, [200, 220], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const lineFinal = frame < 200 ? lineOpacity : lineFadeOut;
  const lineWidth = interpolate(frame, [150, 210], [0, 600], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Question at local frame 180 (global 450)
  const q1Opacity = interpolate(frame, [180, 210], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const q1FadeOut = interpolate(frame, [235, 260], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const q1Final = frame < 235 ? q1Opacity : q1FadeOut;

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
      gap: 20,
    }}>
      <div style={{
        opacity: line1Final,
        transform: `translateY(${line1Y}px)`,
        fontSize: 72,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.02em',
      }}>
        But real learning
      </div>

      <div style={{
        opacity: line2Final,
        transform: `translateY(${line2Y}px)`,
        fontSize: 72,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.02em',
      }}>
        comes from the struggle.
      </div>

      <div style={{
        opacity: lineFinal,
        width: lineWidth,
        height: 1,
        background: '#374151',
        margin: '16px 0',
      }} />

      <div style={{
        opacity: q1Final,
        fontSize: 36,
        color: '#9ca3af',
        fontStyle: 'italic',
        fontWeight: 300,
        textAlign: 'center',
        maxWidth: 900,
      }}>
        Does giving answers... teach anything?
      </div>
    </div>
  );
};
