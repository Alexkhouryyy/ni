import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { MODES, OrbVisual } from './modeColors';

export const MS_AllModes: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade
  const sceneIn = interpolate(frame, [0, 25], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [420, 450], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 420 ? sceneIn : sceneOut;

  // Each orb springs in staggered
  const orbSprings = MODES.map((_, i) =>
    spring({ frame: frame - (20 + i * 30), fps, config: { damping: 16, stiffness: 70 } })
  );
  const orbScales = orbSprings.map(s => interpolate(s, [0, 1], [0, 1]));
  const orbOpacities = MODES.map((_, i) =>
    interpolate(frame, [20 + i * 30, 45 + i * 30], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  );

  // Mode labels appear after orbs
  const labelOpacity = interpolate(frame, [220, 260], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "Which one do you need first?" — big question
  const questionOpacity = interpolate(frame, [280, 320], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const questionY = interpolate(frame, [280, 320], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Pulse per mode (offset each)
  const pulses = MODES.map((_, i) => (Math.sin(frame * 0.07 + i * 1.05) + 1) / 2);

  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#000000',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      opacity: sceneOpacity,
    }}>
      {/* All 6 orbs in a row */}
      <div style={{
        display: 'flex',
        gap: 48,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 40,
      }}>
        {MODES.map((mode, i) => (
          <div key={mode.id} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
            opacity: orbOpacities[i],
            transform: `scale(${orbScales[i]})`,
          }}>
            <OrbVisual color={mode.color} colorLight={mode.colorLight} pulse={pulses[i]} size={120} />
            <div style={{
              opacity: labelOpacity,
              fontSize: 13,
              color: mode.color,
              letterSpacing: '0.05em',
              fontWeight: 600,
              textAlign: 'center',
            }}>
              {mode.name}
            </div>
          </div>
        ))}
      </div>

      {/* Question */}
      <div style={{
        opacity: questionOpacity,
        transform: `translateY(${questionY}px)`,
        textAlign: 'center',
        marginTop: 16,
      }}>
        <div style={{
          fontSize: 52,
          fontWeight: 700,
          color: '#ffffff',
          letterSpacing: '-0.02em',
          marginBottom: 12,
        }}>
          Which one do you need first?
        </div>
        <div style={{
          fontSize: 20,
          color: '#4b5563',
          fontWeight: 300,
        }}>
          Each mode lives in JARVIS — ready to toggle on demand.
        </div>
      </div>
    </div>
  );
};
