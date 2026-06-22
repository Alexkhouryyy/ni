import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

const ChatBubble: React.FC<{
  text: string;
  isUser: boolean;
  opacity: number;
  translateX: number;
}> = ({ text, isUser, opacity, translateX }) => {
  return (
    <div style={{
      opacity,
      transform: `translateX(${translateX}px)`,
      maxWidth: 720,
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      background: isUser ? '#1a1a2e' : '#0f0f1a',
      border: isUser ? '1px solid #374151' : '2px solid #6366f1',
      borderRadius: 16,
      padding: '16px 24px',
    }}>
      {!isUser && (
        <div style={{
          fontSize: 11,
          color: '#6366f1',
          fontWeight: 600,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}>
          JARVIS — Study Mode
        </div>
      )}
      <div style={{
        fontSize: 28,
        color: '#ffffff',
        fontWeight: isUser ? 500 : 600,
        lineHeight: 1.5,
      }}>
        {text}
      </div>
    </div>
  );
};

export const V2_Scene06_Demo2: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [330, 358], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 330 ? sceneIn : sceneOut;

  // User bubble at local frame 30 (global 1470)
  const userSpring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 100 } });
  const userX = interpolate(userSpring, [0, 1], [80, 0]);
  const userOpacity = interpolate(frame, [30, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS refusal at local frame 150 (global 1590)
  const jarvisSpring = spring({ frame: frame - 150, fps, config: { damping: 20, stiffness: 100 } });
  const jarvisX = interpolate(jarvisSpring, [0, 1], [-80, 0]);
  const jarvisOpacity = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // "The refusal IS the lesson." at local frame 240 (global 1680)
  const refusalOpacity = interpolate(frame, [240, 265], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Pulse the refusal line (local frame 300 — global 1740)
  const pulseSin = Math.sin((frame - 300) * 0.15);
  const pulseOpacity = frame >= 300
    ? interpolate(pulseSin, [-1, 1], [0.7, 1.0])
    : refusalOpacity;

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
      padding: '0 200px',
    }}>
      {/* Chat header */}
      <div style={{
        fontSize: 14,
        color: '#374151',
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
        fontWeight: 500,
        marginBottom: 40,
      }}>
        Study Session — Active
      </div>

      {/* Chat messages */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        width: '100%',
        maxWidth: 900,
      }}>
        <ChatBubble
          text="Just tell me the answer."
          isUser={true}
          opacity={userOpacity}
          translateX={userX}
        />
        <ChatBubble
          text="Not in study mode, sir. Work through it."
          isUser={false}
          opacity={jarvisOpacity}
          translateX={jarvisX}
        />
      </div>

      {/* "The refusal IS the lesson." */}
      <div style={{
        opacity: pulseOpacity,
        fontSize: 28,
        color: '#6366f1',
        fontStyle: 'italic',
        fontWeight: 500,
        marginTop: 48,
        letterSpacing: '0.01em',
      }}>
        The refusal IS the lesson.
      </div>
    </div>
  );
};
