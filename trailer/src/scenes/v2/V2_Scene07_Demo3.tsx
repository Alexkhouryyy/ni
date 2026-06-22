import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

const ChatBubble: React.FC<{
  text: string;
  isUser: boolean;
  opacity: number;
  translateX: number;
  fontSize?: number;
}> = ({ text, isUser, opacity, translateX, fontSize = 24 }) => {
  return (
    <div style={{
      opacity,
      transform: `translateX(${translateX}px)`,
      maxWidth: 760,
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
        fontSize,
        color: '#ffffff',
        fontWeight: isUser ? 500 : 400,
        lineHeight: 1.55,
      }}>
        {text}
      </div>
    </div>
  );
};

export const V2_Scene07_Demo3: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene fade in
  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [265, 295], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < 265 ? sceneIn : sceneOut;

  // User explanation at local frame 30 (global 1830)
  const userSpring = spring({ frame: frame - 30, fps, config: { damping: 20, stiffness: 100 } });
  const userX = interpolate(userSpring, [0, 1], [80, 0]);
  const userOpacity = interpolate(frame, [30, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // JARVIS follow-up at local frame 150 (global 1950)
  const jarvisSpring = spring({ frame: frame - 150, fps, config: { damping: 20, stiffness: 100 } });
  const jarvisX = interpolate(jarvisSpring, [0, 1], [-80, 0]);
  const jarvisOpacity = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Caption at local frame 240 (global 2040)
  const captionOpacity = interpolate(frame, [240, 260], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
        maxWidth: 940,
      }}>
        <ChatBubble
          text="A recursive function calls itself to solve a smaller version of the same problem."
          isUser={true}
          opacity={userOpacity}
          translateX={userX}
          fontSize={24}
        />
        <ChatBubble
          text="Good. Now explain why that needs a base case."
          isUser={false}
          opacity={jarvisOpacity}
          translateX={jarvisX}
          fontSize={26}
        />
      </div>

      {/* Caption */}
      <div style={{
        opacity: captionOpacity,
        fontSize: 22,
        color: '#a5b4fc',
        fontStyle: 'italic',
        marginTop: 48,
      }}>
        Understanding tested. Not assumed.
      </div>
    </div>
  );
};
