import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

export interface ModeConfig {
  id: string;
  name: string;
  tag: string;
  color: string;
  colorLight: string;
  tagline: string;
  userMsg: string;
  jarvisMsg: string;
  insight: string;
}

export const MODES: ModeConfig[] = [
  {
    id: 'focus',
    name: 'Focus Mode',
    tag: 'Amber · Pure Execution',
    color: '#f59e0b',
    colorLight: '#fcd34d',
    tagline: 'No tangents. No small talk. Pure execution.',
    userMsg: 'Hey, what did you think of that movie last night?',
    jarvisMsg: 'You have 3 open tasks. That\'s off-topic. What\'s your next action?',
    insight: 'Every response moves the needle.',
  },
  {
    id: 'brutal',
    name: 'Brutal Honesty',
    tag: 'Crimson · No Filter',
    color: '#ef4444',
    colorLight: '#fca5a5',
    tagline: 'Harsh truth. No flattery. Every flaw exposed.',
    userMsg: 'Here\'s my startup pitch. What do you think?',
    jarvisMsg: 'Three problems. Market size unsubstantiated. Moat non-existent. Pricing makes no sense. Start with the market.',
    insight: 'The truth that stings is the truth that saves you.',
  },
  {
    id: 'health',
    name: 'Health Coach',
    tag: 'Lime · Wellness Focus',
    color: '#22c55e',
    colorLight: '#86efac',
    tagline: 'Sleep. Nutrition. Movement. Accountability.',
    userMsg: 'I\'ve been exhausted and can\'t focus lately.',
    jarvisMsg: 'How many hours did you sleep last night, and what did you eat before noon?',
    insight: 'Small consistent actions build extraordinary lives.',
  },
  {
    id: 'debate',
    name: 'Debate Mode',
    tag: 'Violet · Devil\'s Advocate',
    color: '#8b5cf6',
    colorLight: '#c4b5fd',
    tagline: 'JARVIS argues against you — on purpose.',
    userMsg: 'I think remote work is better for productivity.',
    jarvisMsg: 'Disagree. Serendipitous hallway conversations are worth more than the commute saved. What\'s your evidence?',
    insight: 'Ideas that survive JARVIS are ideas worth keeping.',
  },
  {
    id: 'executive',
    name: 'Executive Mode',
    tag: 'Sky Blue · C-Suite Brief',
    color: '#0ea5e9',
    colorLight: '#7dd3fc',
    tagline: 'Maximum signal, zero noise.',
    userMsg: 'Give me a summary of our Q3 situation.',
    jarvisMsg: '▸ Revenue: on track. ▸ Risk: hiring pipeline stalled. ▸ Action: decide contractor vs FTE by Friday.',
    insight: 'Clarity at the speed of thought.',
  },
  {
    id: 'venting',
    name: 'Venting Mode',
    tag: 'Rose · Just Listen',
    color: '#f43f5e',
    colorLight: '#fda4af',
    tagline: 'No solutions. Just presence.',
    userMsg: 'I\'m so tired of everything going wrong.',
    jarvisMsg: 'That sounds genuinely exhausting. You\'ve been carrying a lot. Do you want to tell me more?',
    insight: 'Sometimes being heard is the only thing that matters.',
  },
];

// Shared orb component — animated with a `pulse` value (0..1 sine wave from parent)
export const OrbVisual: React.FC<{
  color: string;
  colorLight: string;
  pulse: number;
  size?: number;
}> = ({ color, colorLight, pulse, size = 220 }) => {
  const scale = 1 + pulse * 0.06;
  const ringScale = 1 + pulse * 0.18;
  const ringOpacity = 0.35 - pulse * 0.25;
  const outerScale = 1 + pulse * 0.35;
  const outerOpacity = 0.12 - pulse * 0.08;

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      {/* Outer glow */}
      <div style={{
        position: 'absolute',
        inset: -size * 0.3,
        borderRadius: '50%',
        background: color,
        filter: `blur(${size * 0.4}px)`,
        opacity: outerOpacity,
        transform: `scale(${outerScale})`,
      }} />
      {/* Ring */}
      <div style={{
        position: 'absolute',
        inset: -size * 0.08,
        borderRadius: '50%',
        border: `1.5px solid ${color}`,
        opacity: ringOpacity,
        transform: `scale(${ringScale})`,
      }} />
      {/* Core */}
      <div style={{
        position: 'absolute',
        inset: size * 0.08,
        borderRadius: '50%',
        background: `radial-gradient(circle at 35% 35%, ${colorLight}, ${color})`,
        transform: `scale(${scale})`,
        boxShadow: `0 0 ${size * 0.3}px ${color}60`,
      }} />
    </div>
  );
};

// Shared chat bubble
export const ChatBubble: React.FC<{
  text: string;
  isUser: boolean;
  opacity: number;
  translateX: number;
  color?: string;
  label?: string;
}> = ({ text, isUser, opacity, translateX, color, label }) => (
  <div style={{
    opacity,
    transform: `translateX(${translateX}px)`,
    maxWidth: 760,
    alignSelf: isUser ? 'flex-end' : 'flex-start',
    background: isUser ? 'rgba(255,255,255,0.05)' : `${color}12`,
    border: isUser ? '1px solid rgba(255,255,255,0.1)' : `1.5px solid ${color}55`,
    borderRadius: 18,
    padding: '18px 26px',
  }}>
    {!isUser && label && (
      <div style={{
        fontSize: 11,
        color,
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        marginBottom: 8,
        opacity: 0.85,
      }}>
        {label}
      </div>
    )}
    <div style={{
      fontSize: isUser ? 28 : 26,
      color: '#ffffff',
      fontWeight: isUser ? 400 : 300,
      lineHeight: 1.55,
      fontStyle: isUser ? 'normal' : 'normal',
    }}>
      {text}
    </div>
  </div>
);
