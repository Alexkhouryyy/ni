import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const V2_Scene01_Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // "In school," fades in at frame 30
  const line1Opacity = interpolate(frame, [30, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1FadeOut = interpolate(frame, [150, 175], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line1FinalOpacity = frame < 150 ? line1Opacity : line1FadeOut;

  const line1TranslateY = interpolate(frame, [30, 55], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "you ask questions." at frame 90
  const line2Opacity = interpolate(frame, [90, 115], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2FadeOut = interpolate(frame, [150, 175], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line2FinalOpacity = frame < 150 ? line2Opacity : line2FadeOut;
  const line2TranslateY = interpolate(frame, [90, 115], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "You get answers." at frame 150
  const line3Opacity = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line3FadeOut = interpolate(frame, [235, 260], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line3FinalOpacity = frame < 235 ? line3Opacity : line3FadeOut;
  const line3TranslateY = interpolate(frame, [150, 175], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Simple." at frame 210
  const line4Opacity = interpolate(frame, [210, 235], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line4FadeOut = interpolate(frame, [245, 270], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const line4FinalOpacity = frame < 245 ? line4Opacity : line4FadeOut;

  const containerStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    background: '#000000',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
    gap: 24,
  };

  return (
    <div style={containerStyle}>
      <div style={{
        opacity: line1FinalOpacity,
        transform: `translateY(${line1TranslateY}px)`,
        fontSize: 72,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.02em',
      }}>
        In school,
      </div>

      <div style={{
        opacity: line2FinalOpacity,
        transform: `translateY(${line2TranslateY}px)`,
        fontSize: 48,
        color: '#9ca3af',
        fontWeight: 400,
      }}>
        you ask questions.
      </div>

      <div style={{
        opacity: line3FinalOpacity,
        transform: `translateY(${line3TranslateY}px)`,
        fontSize: 88,
        color: '#ffffff',
        fontWeight: 700,
        letterSpacing: '-0.03em',
        marginTop: 16,
      }}>
        You get answers.
      </div>

      <div style={{
        opacity: line4FinalOpacity,
        fontSize: 40,
        color: '#6b7280',
        fontStyle: 'italic',
        fontWeight: 300,
      }}>
        Simple.
      </div>
    </div>
  );
};
