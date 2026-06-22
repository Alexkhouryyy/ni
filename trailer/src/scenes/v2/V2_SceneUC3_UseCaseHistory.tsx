import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

const ChatBubble: React.FC<{
  text: string;
  isUser: boolean;
  opacity: number;
  translateX: number;
  accentColor?: string;
}> = ({ text, isUser, opacity, translateX, accentColor = '#f59e0b' }) => {
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

export const V2_SceneUC3_UseCaseHistory: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 300;
  const accentColor = '#f59e0b';

  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [duration - 30, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < duration - 30 ? sceneIn : sceneOut;

  const labelOpacity = interpolate(frame, [5, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // User bubble 1 at frame 30
  const user1Spring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 100 } });
  const user1X = interpolate(user1Spring, [0, 1], [80, 0]);
  const user1Opacity = interpolate(frame, [30, 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS bubble at frame 100
  const jarvis1Spring = spring({ frame: frame - 100, fps, config: { damping: 20, stiffness: 100 } });
  const jarvis1X = interpolate(jarvis1Spring, [0, 1], [-80, 0]);
  const jarvis1Opacity = interpolate(frame, [100, 120], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // User bubble 2 at frame 190
  const user2Spring = spring({ frame: frame - 190, fps, config: { damping: 20, stiffness: 100 } });
  const user2X = interpolate(user2Spring, [0, 1], [80, 0]);
  const user2Opacity = interpolate(frame, [190, 210], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
        USE CASE — HISTORY
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
          text="Why did Rome fall?"
          isUser={true}
          opacity={user1Opacity}
          translateX={user1X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="Which theory interests you most — military, economic, or political? Pick one and defend it."
          isUser={false}
          opacity={jarvis1Opacity}
          translateX={jarvis1X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="Economic. Trade routes collapsed, currency was debased..."
          isUser={true}
          opacity={user2Opacity}
          translateX={user2X}
          accentColor={accentColor}
        />
        <ChatBubble
          text="Strong start. How did currency debasement affect military funding?"
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
        A question that opens ten more.
      </div>
    </div>
  );
};
