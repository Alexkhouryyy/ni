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
      maxWidth: 700,
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      background: isUser ? '#1a1a2e' : '#0f0f1a',
      border: isUser ? '1px solid #374151' : '1.5px solid #6366f1',
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

export const V2_Scene05_Demo1: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [325, 355], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 325 ? sceneIn : sceneOut;

  // User bubble at local frame 30 (global 1110)
  const userSpring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 100 } });
  const userX = interpolate(userSpring, [0, 1], [80, 0]);
  const userOpacity = interpolate(frame, [30, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS bubble at local frame 150 (global 1230)
  const jarvisSpring = spring({ frame: frame - 150, fps, config: { damping: 20, stiffness: 100 } });
  const jarvisX = interpolate(jarvisSpring, [0, 1], [-80, 0]);
  const jarvisOpacity = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Caption at local frame 240 (global 1320)
  const captionOpacity = interpolate(frame, [240, 265], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
          text="What is recursion?"
          isUser={true}
          opacity={userOpacity}
          translateX={userX}
        />
        <ChatBubble
          text="Before I explain — what do YOU think it might mean?"
          isUser={false}
          opacity={jarvisOpacity}
          translateX={jarvisX}
        />
      </div>

      {/* Caption */}
      <div style={{
        opacity: captionOpacity,
        fontSize: 20,
        color: '#6b7280',
        fontStyle: 'italic',
        marginTop: 48,
      }}>
        Not an answer. A question back.
      </div>
    </div>
  );
};
