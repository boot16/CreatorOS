import React from 'react';

/** Circular radial score. size / stroke configurable. */
export default function RadialScore({ value = 0, size = 96, stroke = 8, label, sublabel, color = '#8A2BE2', testId }) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (clamped / 100) * c;
  return (
    <div className="relative inline-flex flex-col items-center" data-testid={testId}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size/2} cy={size/2} r={r}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={c} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 900ms cubic-bezier(0.22, 1, 0.36, 1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-display font-bold text-white leading-none" style={{ fontSize: size * 0.32 }}>
          {Math.round(clamped)}
        </div>
        {sublabel && <div className="text-[10px] uppercase tracking-widest text-zinc-500 mt-1">{sublabel}</div>}
      </div>
      {label && <div className="mt-2 text-xs text-zinc-400">{label}</div>}
    </div>
  );
}
