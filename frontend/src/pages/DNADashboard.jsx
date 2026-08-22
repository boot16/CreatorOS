import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, API, DEMO_CREATOR_ID } from '../lib/api';
import Avatar from '../components/Avatar';
import { Users, Sparkles, Share2, Download, Copy } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';

export default function DNADashboard() {
  const [c, setC] = useState(null);
  const [isReal, setIsReal] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [me, setMe] = useState(null);

  useEffect(() => {
    // Try user's own DNA first; fall back to seeded Alex
    api.get('/me/creator').then(r => {
      setC({ ...r.data, historical_videos: r.data.historical_videos || [] });
      setIsReal(true);
    }).catch(() => {
      api.get(`/creators/${DEMO_CREATOR_ID}`).then(r => setC(r.data));
    });
    api.get('/auth/status').then(r => setMe(r.data.user)).catch(() => {});
    if (new URLSearchParams(window.location.search).get('connected') === '1') {
      toast.success('YouTube connected — real DNA loaded.');
    }
  }, []);

  const dnaCreatorId = isReal ? 'me' : DEMO_CREATOR_ID;
  const cardUrl = `${API}/dna-card/${isReal ? DEMO_CREATOR_ID : DEMO_CREATOR_ID}.png`; // Real user card TODO — for now server-render uses seeded only
  const copyLink = () => { navigator.clipboard.writeText(cardUrl); toast('Link copied'); };
  const downloadPng = () => {
    const a = document.createElement('a');
    a.href = cardUrl; a.download = 'creator-dna.png'; document.body.appendChild(a); a.click(); a.remove();
  };

  if (!c) return <div className="text-zinc-400">Loading DNA…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} data-testid="dna-dashboard">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="flex items-center gap-4">
          <Avatar gradient={c.avatar_gradient} initials={c.initials} size={56} />
          <div>
            <div className="text-xs uppercase tracking-widest text-violet-300 flex items-center gap-2">
              Creator DNA
              {isReal && <span className="chip chip-accent text-[9px] px-2" data-testid="real-dna-chip">Your channel</span>}
            </div>
            <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">{c.name}</h1>
            <div className="text-zinc-500 text-sm">{c.handle} · {c.niche} · {(c.subscribers/1000).toFixed(0)}K subs</div>
          </div>
        </div>
        <button data-testid="share-dna-btn" onClick={() => setShareOpen(true)} className="btn-primary inline-flex items-center gap-2">
          <Share2 size={14} /> Share DNA
        </button>
      </div>

      {me?.youtube_channel && (
        <div className="mt-4 chip chip-accent" data-testid="youtube-connected-chip">
          Connected · {me.youtube_channel.title} ({(me.youtube_channel.subscribers/1000).toFixed(0)}K)
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4 mt-8">
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
                  <motion.div initial={{ width: 0 }} animate={{ width: `${p.pct * 2.5}%` }} transition={{ duration: 0.9, ease: 'easeOut' }} className="h-full rounded-full" style={{ background: 'linear-gradient(90deg, #8A2BE2, #C4B5FD)' }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card-surface p-6">
          <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-5">Format multipliers</h3>
          <div className="space-y-3">
            {c.formats.map(f => (
              <div key={f.name} className="flex items-center justify-between" data-testid={`format-${f.name.replace(/ /g,'-').toLowerCase()}`}>
                <div>
                  <div className="text-sm text-zinc-200">{f.name}</div>
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500">{f.label}</div>
                </div>
                <div className="font-display font-semibold text-lg" style={{ color: f.multiplier >= 1.5 ? '#10B981' : f.multiplier >= 1 ? '#F8F9FA' : '#EF4444' }}>{f.multiplier}×</div>
              </div>
            ))}
          </div>
        </div>

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

        <div className="card-surface p-6">
          <div className="flex items-center gap-2 mb-5">
            <Users size={14} className="text-violet-300" />
            <h3 className="font-display text-base font-semibold uppercase tracking-widest">Audience interests</h3>
          </div>
          <div className="space-y-3">
            {c.audience_interests.map(a => (
              <div key={a.name}>
                <div className="flex justify-between text-sm mb-1"><span className="text-zinc-200">{a.name}</span><span className="text-zinc-500 font-mono">{a.affinity}</span></div>
                <div className="h-1.5 rounded-full bg-white/5">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${a.affinity}%` }} transition={{ duration: 0.8 }} className="h-full rounded-full bg-violet-500" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

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

      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent className="max-w-2xl border-white/10" style={{ background: '#12121A' }} data-testid="share-dna-modal">
          <DialogHeader><DialogTitle className="font-display text-xl">Share your Creator DNA</DialogTitle></DialogHeader>
          <div className="rounded-xl overflow-hidden border border-white/10">
            <img src={cardUrl} alt="Creator DNA card" className="w-full block" data-testid="dna-card-preview" />
          </div>
          <div className="flex flex-wrap gap-2 mt-4">
            <button onClick={downloadPng} data-testid="dna-download-btn" className="btn-primary inline-flex items-center gap-2">
              <Download size={14} /> Download PNG
            </button>
            <button onClick={copyLink} data-testid="dna-copy-link-btn" className="btn-ghost inline-flex items-center gap-2">
              <Copy size={14} /> Copy image URL
            </button>
            <a href={`https://twitter.com/intent/tweet?text=${encodeURIComponent('My CreatorOS DNA →')}&url=${encodeURIComponent(cardUrl)}`}
               target="_blank" rel="noreferrer" className="btn-ghost">Share on X</a>
          </div>
          <div className="text-xs text-zinc-500 mt-2">1200 × 675 · optimized for X, LinkedIn, and blog embeds.</div>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
