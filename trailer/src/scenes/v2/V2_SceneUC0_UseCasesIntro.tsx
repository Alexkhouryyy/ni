import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const V2_SceneUC0_UseCasesIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 180;

  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [duration - 30, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < duration - 30 ? sceneIn : sceneOut;

  // "Study Mode" label fades in at frame 20
  const labelOpacity = interpolate(frame, [20, 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "works for every subject" springs in at frame 45
  const line1Spring = spring({ frame: frame - 45, fps, config: { damping: 20, stiffness: 100 } });
  const line1Y = interpolate(line1Spring, [0, 1], [40, 0]);
  const line1Opacity = interpolate(frame, [45, 65], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "you want to master." springs in at frame 100
  const line2Spring = spring({ frame: frame - 100, fps, config: { damping: 20, stiffness: 100 } });
  const line2Y = interpolate(line2Spring, [0, 1], [40, 0]);
  const line2Opacity = interpolate(frame, [100, 120], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Subject labels appear at frame 140
  const labelsOpacity = interpolate(frame, [140, 160], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const subjects = [
    { label: 'Coding', color: '#4fc3f7' },
    { label: 'Mathematics', color: '#34d399' },
    { label: 'History', color: '#f59e0b' },
    { label: 'Languages', color: '#f472b6' },
  ];

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
      {/* "Study Mode" label */}
      <div style={{
        opacity: labelOpacity,
        fontSize: 40,
        color: '#6366f1',
        letterSpacing: '0.2em',
        textTransform: 'uppercase',
        fontWeight: 600,
        marginBottom: 24,
      }}>
        Study Mode
      </div>

      {/* "works for every subject" */}
      <div style={{
        opacity: line1Opacity,
        transform: `translateY(${line1Y}px)`,
        fontSize: 72,
        color: '#ffffff',
        fontWeight: 700,
        marginBottom: 8,
      }}>
        works for every subject
      </div>

      {/* "you want to master." */}
      <div style={{
        opacity: line2Opacity,
        transform: `translateY(${line2Y}px)`,
        fontSize: 72,
        color: '#ffffff',
        fontWeight: 700,
        marginBottom: 60,
      }}>
        you want to master.
      </div>

      {/* Subject labels row */}
      <div style={{
        opacity: labelsOpacity,
        display: 'flex',
        flexDirection: 'row',
        gap: 0,
      }}>
        {subjects.map((subject, i) => (
          <div
            key={subject.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: 200,
              justifyContent: 'center',
            }}
          >
            <div style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: subject.color,
              flexShrink: 0,
            }} />
            <span style={{
              fontSize: 24,
              color: '#9ca3af',
              fontWeight: 500,
            }}>
              {subject.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
