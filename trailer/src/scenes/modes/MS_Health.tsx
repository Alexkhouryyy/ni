import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { MODES, OrbVisual, ChatBubble } from './modeColors';

const MODE = MODES[2]; // Health Coach

export const MS_Health: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [695, 720], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 695 ? sceneIn : sceneOut;

  const nameIn = interpolate(frame, [30, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const nameY = interpolate(frame, [30, 60], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const orbSpring = spring({ frame: frame - 50, fps, config: { damping: 18, stiffness: 80 } });
  const orbScale = interpolate(orbSpring, [0, 1], [0.4, 1]);
  const orbOpacity = interpolate(frame, [50, 80], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const tagIn = interpolate(frame, [100, 130], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const tagY = interpolate(frame, [100, 130], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const pulse = (Math.sin(frame * 0.06) + 1) / 2;

  const userSpring = spring({ frame: frame - 160, fps, config: { damping: 20, stiffness: 100 } });
  const userX = interpolate(userSpring, [0, 1], [80, 0]);
  const userOpacity = interpolate(frame, [160, 185], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const jarvisSpring = spring({ frame: frame - 280, fps, config: { damping: 20, stiffness: 100 } });
  const jarvisX = interpolate(jarvisSpring, [0, 1], [-80, 0]);
  const jarvisOpacity = interpolate(frame, [280, 305], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const insightOpacity = interpolate(frame, [420, 450], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#000000',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      opacity: sceneOpacity,
      padding: '0 180px',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, transparent, ${MODE.color}, transparent)`, opacity: nameIn }} />

      <div style={{ opacity: nameIn, transform: `translateY(${nameY}px)`, textAlign: 'center', marginBottom: 36 }}>
        <div style={{ fontSize: 16, color: MODE.color, letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 600, marginBottom: 8 }}>{MODE.tag}</div>
        <div style={{ fontSize: 72, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', lineHeight: 1 }}>{MODE.name}</div>
      </div>

      <div style={{ opacity: orbOpacity, transform: `scale(${orbScale})`, marginBottom: 32 }}>
        <OrbVisual color={MODE.color} colorLight={MODE.colorLight} pulse={pulse} size={180} />
      </div>

      <div style={{ opacity: tagIn, transform: `translateY(${tagY}px)`, fontSize: 26, color: '#6b7280', fontWeight: 300, textAlign: 'center', marginBottom: 56 }}>
        {MODE.tagline}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18, width: '100%', maxWidth: 900 }}>
        <ChatBubble text={MODE.userMsg} isUser={true} opacity={userOpacity} translateX={userX} />
        <ChatBubble text={MODE.jarvisMsg} isUser={false} opacity={jarvisOpacity} translateX={jarvisX} color={MODE.color} label={`JARVIS — ${MODE.name}`} />
      </div>

      <div style={{ opacity: insightOpacity, fontSize: 20, color: '#4b5563', fontStyle: 'italic', marginTop: 40 }}>{MODE.insight}</div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, transparent, ${MODE.color}, transparent)`, opacity: nameIn * 0.5 }} />
    </div>
  );
};
