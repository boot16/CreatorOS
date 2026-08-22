import React from 'react';
import { useBootstrap } from '../lib/bootstrap';

/** Subtle badge shown in demo mode; hidden in production. */
export default function DemoBadge() {
  const { data_mode, is_demo } = useBootstrap();
  if (!is_demo && data_mode !== 'demo') return null;
  return (
    <div
      data-testid="demo-badge"
      className="fixed bottom-4 left-4 z-40 px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest font-medium flex items-center gap-2"
      style={{
        background: 'rgba(138,43,226,0.16)',
        border: '1px solid rgba(138,43,226,0.45)',
        color: '#C4B5FD',
        backdropFilter: 'blur(12px)',
      }}
      title="This is seeded demo data — not a real creator's analytics."
    >
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
      Demo data
    </div>
  );
}
