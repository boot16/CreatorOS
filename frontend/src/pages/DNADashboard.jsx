import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, DEMO_CREATOR_ID } from '../lib/api';
import Avatar from '../components/Avatar';
import { Users, Sparkles } from 'lucide-react';

export default function DNADashboard() {
  const [c, setC] = useState(null);

  useEffect(() => {
    api.get(`/creators/${DEMO_CREATOR_ID}`).then(r => setC(r.data));
  }, []);

  if (!c) return <div className="text-zinc-400">Loading DNA…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} data-testid="dna-dashboard">
      <div className="flex items-center gap-4 mb-2">
        <Avatar gradient={c.avatar_gradient} initials={c.initials} size={56} />
        <div>
          <div className="text-xs uppercase tracking-widest text-violet-300">Creator DNA</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">{c.name}</h1>
          <div className="text-zinc-500 text-sm">{c.handle} · {c.niche} · {(c.subscribers/1000).toFixed(0)}K subs</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-8">
        {/* Pillars */}
        <div className="card-surface p-6 lg:col-span-2">
          <div className="flex items-center gap-2 mb-5">
            <Sparkles size={14} className="text-violet-300" />
            <h3 className="font-display text-base font-semibold uppercase tracking-widest">Content pillars</h3>
          </div>
          <div className="space-y-4">
            {c.pillars.map(p => (
              <div key={p.name} data-testid={`pillar-${p.name.replace(/ /g,'-').toLowerCase()}`}>
                <div className="flex justify-between text-sm mb-1.5">
                  <span className="text-zinc-200">{p.name}</span>
                  <span className="text-zinc-500 font-mono">{p.pct}%</span>
                </div>
                <div className="h-2 rounded-full overflow-hidden bg-white/5">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${p.pct * 2.5}%` }}
                    transition={{ duration: 0.9, ease: 'easeOut' }}
                    className="h-full rounded-full"
                    style={{ background: 'linear-gradient(90deg, #8A2BE2, #C4B5FD)' }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Formats */}
        <div className="card-surface p-6">
          <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-5">Format multipliers</h3>
          <div className="space-y-3">
            {c.formats.map(f => (
              <div key={f.name} className="flex items-center justify-between" data-testid={`format-${f.name.replace(/ /g,'-').toLowerCase()}`}>
                <div>
                  <div className="text-sm text-zinc-200">{f.name}</div>
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500">{f.label}</div>
                </div>
                <div
                  className="font-display font-semibold text-lg"
                  style={{ color: f.multiplier >= 1.5 ? '#10B981' : f.multiplier >= 1 ? '#F8F9FA' : '#EF4444' }}
                >
                  {f.multiplier}×
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Style */}
        <div className="card-surface p-6 lg:col-span-2">
          <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-5">Voice & style fingerprint</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            {Object.entries(c.style).map(([k, v]) => (
              <div key={k} className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{k}</div>
                <div className="text-sm text-zinc-200">{v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Audience */}
        <div className="card-surface p-6">
          <div className="flex items-center gap-2 mb-5">
            <Users size={14} className="text-violet-300" />
            <h3 className="font-display text-base font-semibold uppercase tracking-widest">Audience interests</h3>
          </div>
          <div className="space-y-3">
            {c.audience_interests.map(a => (
              <div key={a.name}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-zinc-200">{a.name}</span>
                  <span className="text-zinc-500 font-mono">{a.affinity}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${a.affinity}%` }} transition={{ duration: 0.8 }} className="h-full rounded-full bg-violet-500" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Historical videos */}
      <div className="mt-10">
        <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4 text-zinc-300">Recent videos</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {c.historical_videos.slice(0, 10).map((v, i) => (
            <div key={i} className="card-surface overflow-hidden card-hover" data-testid={`video-${i}`}>
              <div className="aspect-video relative" style={{ background: `linear-gradient(135deg, ${v.grad[0]}, ${v.grad[1]})` }}>
                <div className="absolute bottom-2 left-2 chip text-white bg-black/50 border-white/10">{v.format}</div>
              </div>
              <div className="p-3">
                <div className="text-xs text-zinc-200 leading-snug line-clamp-2">{v.title}</div>
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mt-2">{(v.views/1000).toFixed(0)}K views</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
