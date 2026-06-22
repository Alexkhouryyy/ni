import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

const ChatBubble: React.FC<{
  text: string;
  isUser: boolean;
  opacity: number;
  translateX: number;
  accentColor?: string;
}> = ({ text, isUser, opacity, translateX, accentColor = '#4fc3f7' }) => {
  return (
    <div style={{
      opacity,
      transform: `translateX(${translateX}px)`,
      maxWidth: 700,
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      background: isUser ? '#1a1a2e' : '#0f0f1a',
      border: isUser ? '1px solid #374151' : `1.5px solid ${accentColor}`,
      borderRadius: 16,
      padding: '16px 24px',
    }}>
      {!isUser && (
        <div style={{
          fontSize: 11,
          color: accentColor,
          fontWeight: 600,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}>
          JARVIS — Study Mode
        </div>
      )}
      <div style={{
        fontSize: isUser ? 28 : 26,
        color: '#ffffff',
        fontWeight: isUser ? 500 : 400,
        lineHeight: 1.5,
      }}>
        {text}
      </div>
    </div>
  );
};

export const V2_SceneUC1_UseCaseCoding: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 300;
  const accentColor = '#4fc3f7';

  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [duration - 30, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < duration - 30 ? sceneIn : sceneOut;

  // Subject label
  const labelOpacity = interpolate(frame, [5, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // User bubble 1 at frame 30
  const user1Spring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 100 } });
  const user1X = interpolate(user1Spring, [0, 1], [80, 0]);
  const user1Opacity = interpolate(frame, [30, 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS bubble at frame 120
  const jarvis1Spring = spring({ frame: frame - 120, fps, config: { damping: 20, stiffness: 100 } });
  const jarvis1X = interpolate(jarvis1Spring, [0, 1], [-80, 0]);
  const jarvis1Opacity = interpolate(frame, [120, 140], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // User bubble 2 at frame 200
  const user2Spring = spring({ frame: frame - 200, fps, config: { damping: 20, stiffness: 100 } });
  const user2X = interpolate(user2Spring, [0, 1], [80, 0]);
  const user2Opacity = interpolate(frame, [200, 220], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS bubble 2 at frame 255
  const jarvis2Spring = spring({ frame: frame - 255, fps, config: { damping: 20, stiffness: 100 } });
  const jarvis2X = interpolate(jarvis2Spring, [0, 1], [-80, 0]);
  const jarvis2Opacity = interpolate(frame, [255, 275], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Caption at frame 280
  const captionOpacity = interpolate(frame, [280, 295], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      position: 'relative',
    }}>
      {/* Subject label top-left */}
      <div style={{
        position: 'absolute',
        top: 60,
        left: 80,
        opacity: labelOpacity,
        fontSize: 14,
        color: accentColor,
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
        fontWeight: 600,
      }}>
        USE CASE — CODING
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
          text="What is a closure in JavaScript?"
          isUser={true}
          opacity={user1Opacity}
          translateX={user1X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="You've used setTimeout in a loop. What did it print — and why?"
          isUser={false}
          opacity={jarvis1Opacity}
          translateX={jarvis1X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="It printed the same number every time... the last value of i."
          isUser={true}
          opacity={user2Opacity}
          translateX={user2X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="Precisely. So a closure captures the variable, not the value. Why does that matter?"
          isUser={false}
          opacity={jarvis2Opacity}
          translateX={jarvis2X}
          accentColor={accentColor}
        />
      </div>

      {/* Caption */}
      <div style={{
        opacity: captionOpacity,
        fontSize: 20,
        color: accentColor,
        fontStyle: 'italic',
        marginTop: 48,
      }}>
        Discovery over explanation.
      </div>
    </div>
  );
};
