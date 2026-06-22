import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const V2_Scene04_Transform: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [240, 265], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 240 ? sceneIn : sceneOut;

  // Left orb (cyan, normal mode) — enters immediately
  const leftOrbSpring = spring({ frame, fps, config: { damping: 22, stiffness: 70 } });
  const leftOrbX = interpolate(leftOrbSpring, [0, 1], [-200, 0]);

  // Right orb (indigo, study mode)
  const rightOrbSpring = spring({ frame: frame - 20, fps, config: { damping: 22, stiffness: 70 } });
  const rightOrbX = interpolate(rightOrbSpring, [0, 1], [200, 0]);

  // "Normal Mode" label at local frame 60 (global 870)
  const leftLabelOpacity = interpolate(frame, [60, 80], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Study Mode" label at local frame 120 (global 930)
  const rightLabelOpacity = interpolate(frame, [120, 140], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Left orb fades at local frame 150 (global 960)
  const leftFadeOut = interpolate(frame, [150, 190], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const leftOpacity = frame < 150 ? 1 : leftFadeOut;

  // Right orb pulse — sine-based
  const pulseSin = Math.sin((frame - 150) * 0.12);
  const pulseScale = frame >= 150 ? interpolate(pulseSin, [-1, 1], [0.95, 1.05]) : 1;
  const pulseGlow = frame >= 150 ? interpolate(pulseSin, [-1, 1], [0.4, 0.8]) : 0.5;

  // "One toggle" text at local frame 210
  const toggleTextSpring = spring({ frame: frame - 210, fps, config: { damping: 20, stiffness: 90 } });
  const toggleTextY = interpolate(toggleTextSpring, [0, 1], [30, 0]);
  const toggleTextOpacity = interpolate(frame, [210, 235], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      {/* Two orbs side by side */}
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 160,
        marginBottom: 60,
      }}>
        {/* Left: Normal Mode */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 24,
          opacity: leftOpacity,
          transform: `translateX(${leftOrbX}px)`,
        }}>
          <div style={{
            opacity: leftLabelOpacity,
            fontSize: 24,
            color: '#4ca8e8',
            fontWeight: 500,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>
            Normal Mode
          </div>
          <div style={{
            width: 200,
            height: 200,
            borderRadius: '50%',
            background: 'radial-gradient(circle, #7dd3fc 0%, #0ea5e9 35%, #0c4a6e 70%, transparent 100%)',
            boxShadow: '0 0 50px 15px rgba(14,165,233,0.4)',
          }} />
        </div>

        {/* Right: Study Mode */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 24,
          transform: `translateX(${rightOrbX}px) scale(${pulseScale})`,
        }}>
          <div style={{
            opacity: rightLabelOpacity,
            fontSize: 24,
            color: '#6366f1',
            fontWeight: 600,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>
            Study Mode
          </div>
          <div style={{
            width: 200,
            height: 200,
            borderRadius: '50%',
            background: 'radial-gradient(circle, #818cf8 0%, #6366f1 35%, #312e81 70%, transparent 100%)',
            boxShadow: `0 0 60px 20px rgba(99,102,241,${pulseGlow})`,
          }} />
        </div>
      </div>

      {/* "One toggle. A new JARVIS." */}
      <div style={{
        opacity: toggleTextOpacity,
        transform: `translateY(${toggleTextY}px)`,
        fontSize: 48,
        color: '#ffffff',
        fontWeight: 600,
        letterSpacing: '-0.02em',
        textAlign: 'center',
      }}>
        One toggle. A new JARVIS.
      </div>
    </div>
  );
};
