import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowRight, Youtube } from 'lucide-react';

const GOALS = [
  { id: 'grow', label: 'Grow subscribers', desc: 'Reach new audience' },
  { id: 'monetize', label: 'Monetize consistently', desc: 'Sponsorships & products' },
  { id: 'collab', label: 'Find collaborators', desc: 'Grow through partnerships' },
  { id: 'trends', label: 'Ride trends earlier', desc: 'Get to topics first' },
  { id: 'workflow', label: 'Ship more consistently', desc: 'Ideas → published, faster' },
];

export default function Onboarding() {
  const nav = useNavigate();
  const [picked, setPicked] = useState(new Set(['grow', 'trends']));

  const toggle = (id) => {
    const s = new Set(picked);
    s.has(id) ? s.delete(id) : s.add(id);
    setPicked(s);
  };

  return (
    <div className="min-h-screen">
      <header className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="onboarding-home">
          <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
          <span className="font-display text-lg font-semibold">CreatorOS</span>
        </Link>
        <span className="text-xs text-zinc-500">Step 1 of 1</span>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="chip chip-accent mb-6">Onboarding</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
          What are you optimizing for?
        </h1>
        <p className="mt-4 text-zinc-400">Pick what matters. This tunes the reasoning shown next to every recommendation.</p>

        <div className="mt-10 grid sm:grid-cols-2 gap-3">
          {GOALS.map(g => {
            const active = picked.has(g.id);
            return (
              <button
                key={g.id}
                onClick={() => toggle(g.id)}
                data-testid={`goal-${g.id}`}
                className="text-left card-surface p-5 card-hover"
                style={ active ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.06)'} : {}}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-display font-semibold text-white">{g.label}</div>
                    <div className="text-sm text-zinc-500 mt-1">{g.desc}</div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border ${active ? 'bg-violet-500 border-violet-400' : 'border-white/20'}`}>
                    {active && <div className="w-full h-full flex items-center justify-center text-white text-[11px]">✓</div>}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-12 flex flex-wrap items-center gap-3">
          <button
            data-testid="explore-demo-btn"
            onClick={() => nav('/dna-reveal')}
            className="btn-primary inline-flex items-center gap-2"
          >
            Explore Demo <ArrowRight size={16} />
          </button>
          <button
            data-testid="connect-youtube-btn"
            onClick={() => toast('Real YouTube OAuth is coming soon — try the seeded demo for now.')}
            className="btn-ghost inline-flex items-center gap-2"
          >
            <Youtube size={16} /> Connect YouTube
          </button>
          <span className="text-xs text-zinc-500 ml-2">No signup required for demo</span>
        </div>
      </div>
    </div>
  );
}
