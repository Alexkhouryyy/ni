import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

interface CardData {
  label: string;
  example: string;
  accentColor: string;
  startFrame: number;
}

const UseCaseCard: React.FC<{
  label: string;
  example: string;
  accentColor: string;
  opacity: number;
  translateY: number;
}> = ({ label, example, accentColor, opacity, translateY }) => {
  return (
    <div style={{
      opacity,
      transform: `translateY(${translateY}px)`,
      width: 380,
      height: 220,
      background: '#0a0a0f',
      border: `1px solid ${accentColor}`,
      borderRadius: 16,
      padding: '28px 32px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      gap: 12,
    }}>
      <div style={{
        fontSize: 18,
        color: accentColor,
        fontWeight: 600,
        letterSpacing: '0.05em',
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 16,
        color: '#6b7280',
        fontWeight: 400,
        lineHeight: 1.5,
      }}>
        {example}
      </div>
    </div>
  );
};

export const V2_SceneUC4_UseCasesBanner: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const duration = 180;

  const sceneIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOut = interpolate(frame, [duration - 30, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sceneOpacity = frame < duration - 30 ? sceneIn : sceneOut;

  // Title fades in at frame 20
  const titleOpacity = interpolate(frame, [20, 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const cards: CardData[] = [
    { label: 'Coding', example: 'closures, async/await, recursion', accentColor: '#4fc3f7', startFrame: 40 },
    { label: 'Mathematics', example: 'proofs, limits, derivatives', accentColor: '#34d399', startFrame: 65 },
    { label: 'History', example: 'causes, context, argument', accentColor: '#f59e0b', startFrame: 90 },
    { label: 'Languages', example: 'grammar, vocabulary, structure', accentColor: '#f472b6', startFrame: 115 },
  ];

  const cardSprings = cards.map(card =>
    spring({ frame: frame - card.startFrame, fps, config: { damping: 20, stiffness: 100 } })
  );

  // Bottom tagline at frame 150
  const taglineOpacity = interpolate(frame, [150, 165], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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
      gap: 40,
    }}>
      {/* Title */}
      <div style={{
        opacity: titleOpacity,
        fontSize: 48,
        color: '#ffffff',
        fontWeight: 700,
        textAlign: 'center',
      }}>
        Any subject. Any level.
      </div>

      {/* 2x2 grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '380px 380px',
        gap: 24,
      }}>
        {cards.map((card, i) => (
          <UseCaseCard
            key={card.label}
            label={card.label}
            example={card.example}
            accentColor={card.accentColor}
            opacity={interpolate(cardSprings[i], [0, 0.3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })}
            translateY={interpolate(cardSprings[i], [0, 1], [40, 0])}
          />
        ))}
      </div>

      {/* Bottom tagline */}
      <div style={{
        opacity: taglineOpacity,
        fontSize: 28,
        color: '#6366f1',
        fontWeight: 600,
        textAlign: 'center',
      }}>
        Socratic method on demand.
      </div>
    </div>
  );
};
