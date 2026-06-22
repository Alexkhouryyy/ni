import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

const FONT_FAMILY = "'SF Pro Display', 'Helvetica Neue', -apple-system, Arial, sans-serif";
const INDIGO = '#6366f1';

// Local frame: 0 = global 270
// Line 1 "Ask, don't answer." — appears at local frame 0
// Line 2 "Make you explain it back." — appears at local frame 25
// Line 3 "No shortcuts." — appears at local frame 50

type FeatureLineProps = {
  text: string;
  color: string;
  fontWeight: number;
  delay: number;
};

const FeatureLine: React.FC<FeatureLineProps> = ({ text, color, fontWeight, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideProgress = spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 60 },
  });

  const opacity = interpolate(frame, [delay, delay + 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const translateY = interpolate(slideProgress, [0, 1], [40, 0]);

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
        fontFamily: FONT_FAMILY,
        fontSize: '72px',
        fontWeight,
        color,
        textAlign: 'center',
        letterSpacing: '-1px',
        lineHeight: 1.15,
      }}
    >
      {text}
    </div>
  );
};

export const Scene03_Features: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000000',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '20px',
      }}
    >
      <FeatureLine
        text="Ask, don't answer."
        color="#ffffff"
        fontWeight={400}
        delay={0}
      />
      <FeatureLine
        text="Make you explain it back."
        color="#ffffff"
        fontWeight={400}
        delay={25}
      />
      <FeatureLine
        text="No shortcuts."
        color={INDIGO}
        fontWeight={700}
        delay={50}
      />
    </AbsoluteFill>
  );
};
