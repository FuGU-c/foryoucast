import React, { type ComponentProps, useId } from 'react';
import './waveform-seek.css';

type WaveformSeekProps = ComponentProps<'input'> & { playing: boolean };

const BAR_COUNT = 90;
const BAR_STEP = 8;
const BAR_WIDTH = 4;
const VIEW_WIDTH = 720;
const VIEW_HEIGHT = 64;

// This is a visual texture, not a measurement of the audio waveform.
const bars = Array.from({ length: BAR_COUNT }, (_, index) => {
  const envelope=.35+.65*Math.pow(Math.sin(index*.12+.8),2);
  const shape=.3+Math.abs(Math.sin(index*.67)*Math.cos(index*.23))*.7;
  const height=8+envelope*shape*34;
  return {
    x: 2 + index * BAR_STEP,
    y: (VIEW_HEIGHT - height) / 2,
    height,
    phase: -((index * 0.037) % 1.48),
    duration: 2.2 + (index % 7) * .15,
  };
});

export function WaveformSeek({ playing, min = 0, max = 100, value = 0, className = '', ...inputProps }: WaveformSeekProps) {
  const id = useId().replace(/:/g, '');
  const lower = Number(min);
  const upper = Number(max);
  const current = Number(value);
  const progress = Number.isFinite(current) && Number.isFinite(lower) && Number.isFinite(upper) && upper > lower
    ? Math.max(0, Math.min(1, (current - lower) / (upper - lower)))
    : 0;

  return <div className={`waveform-seek${playing ? ' is-playing' : ''}`}>
    <svg className="waveform-seek-art" viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-progress`} gradientUnits="userSpaceOnUse" x1="0" x2={VIEW_WIDTH} y1="0" y2="0">
          <stop offset="0%" stopColor="var(--theme-secondary)" />
          <stop offset="100%" stopColor="var(--theme-secondary)" />
        </linearGradient>
        <clipPath id={`${id}-clip`}>
          <rect x="0" y="0" width={VIEW_WIDTH * progress} height={VIEW_HEIGHT} />
        </clipPath>
      </defs>
      <g className="waveform-seek-bars">
        {bars.map((bar, index) => <rect key={index} className="waveform-seek-bar" x={bar.x} y={bar.y} width={BAR_WIDTH} height={bar.height} rx={BAR_WIDTH / 2} style={{ animationDelay: `${bar.phase}s`, animationDuration: `${bar.duration}s` }} />)}
      </g>
      <g className="waveform-seek-played" clipPath={`url(#${id}-clip)`}>
        {bars.map((bar, index) => <rect key={index} className="waveform-seek-bar" x={bar.x} y={bar.y} width={BAR_WIDTH} height={bar.height} rx={BAR_WIDTH / 2} style={{ animationDelay: `${bar.phase}s`, animationDuration: `${bar.duration}s`, fill: `url(#${id}-progress)` }} />)}
      </g>
    </svg>
    <span className="waveform-playhead" aria-hidden="true" style={{left:`calc(8px + (100% - 16px) * ${progress})`}}/>
    <input {...inputProps} className={`seek-range waveform-seek-input ${className}`.trim()} type="range" min={min} max={max} value={value} />
  </div>;
}
