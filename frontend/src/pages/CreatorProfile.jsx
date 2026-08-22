import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, DEMO_CREATOR_ID, SECOND_CREATOR_ID } from '../lib/api';
import RadialScore from '../components/RadialScore';
import Avatar from '../components/Avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Send, MessageSquare } from 'lucide-react';

const LABEL = {
  AudienceCompat: 'Audience overlap',
  TopicCompat: 'Topic overlap',
  ContentComplementarity: 'Complementarity',
  CreatorSizeCompat: 'Size compatibility',
  FormatCompat: 'Format compatibility',
};

export default function CreatorProfile() {
  const [sarah, setSarah] = useState(null);
  const [compat, setCompat] = useState(null);
  const [open, setOpen] = useState(false);
  const [proposal, setProposal] = useState({ idea: '', message: '' });
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.get(`/creators/${SECOND_CREATOR_ID}`).then(r => setSarah(r.data));
    api.get(`/compatibility/${DEMO_CREATOR_ID}/${SECOND_CREATOR_ID}`).then(r => setCompat(r.data));
  }, []);

  const submit = async () => {
    setSending(true);
    try {
      await api.post('/collab-proposal', {
        from_creator_id: DEMO_CREATOR_ID,
        to_creator_id: SECOND_CREATOR_ID,
        idea: proposal.idea, message: proposal.message,
      });
      toast.success('Proposal sent to Sarah (demo — no real message).');
      setOpen(false);
      setProposal({ idea: '', message: '' });
    } catch { toast.error('Something went wrong.'); }
    setSending(false);
  };

  if (!sarah || !compat) return <div className="text-zinc-500">Loading collab…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="creator-profile">
      <div className="grid lg:grid-cols-[1fr_360px] gap-8">
        <div>
          <div className="chip chip-accent mb-4">Best collaborator match</div>
          <div className="flex items-start gap-5">
            <Avatar gradient={sarah.avatar_gradient} initials={sarah.initials} size={80} />
            <div>
              <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">{sarah.name}</h1>
              <div className="text-zinc-500 text-sm mt-1">{sarah.handle} · {sarah.niche} · {(sarah.subscribers/1000).toFixed(0)}K subs</div>
              <p className="text-zinc-300 mt-4 max-w-lg leading-relaxed">{sarah.bio}</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4 mt-10">
            <div className="card-surface p-6">
              <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Content pillars</h3>
              <div className="space-y-3">
                {sarah.pillars.map(p => (
                  <div key={p.name}>
                    <div className="flex justify-between text-sm mb-1"><span>{p.name}</span><span className="text-zinc-500 font-mono">{p.pct}%</span></div>
                    <div className="h-1.5 bg-white/5 rounded-full">
                      <div className="h-full rounded-full" style={{ width: `${p.pct * 2.5}%`, background: 'linear-gradient(90deg,#F59E0B,#FDE68A)' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card-surface p-6">
              <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Why this collab works</h3>
              <ul className="space-y-3">
                {compat.why_bullets.map((b, i) => (
                  <li key={i} className="flex gap-3 text-sm text-zinc-200" data-testid={`compat-why-${i}`}>
                    <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0 bg-violet-400" />
                    {b}
                  </li>
                ))}
              </ul>
            </div>

            <div className="card-surface p-6 md:col-span-2">
              <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Collab ideas</h3>
              <div className="grid sm:grid-cols-3 gap-3">
                {compat.collab_ideas.map((idea, i) => (
                  <button
                    key={i}
                    onClick={() => { setProposal(p => ({ ...p, idea })); setOpen(true); }}
                    data-testid={`collab-idea-${i}`}
                    className="text-left p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:border-violet-500/50 transition-colors"
                  >
                    <div className="text-[10px] uppercase tracking-widest text-violet-300 mb-2">Idea {i+1}</div>
                    <div className="text-sm text-zinc-200 leading-snug">{idea}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="card-surface p-6 sticky top-24">
            <div className="flex flex-col items-center">
              <RadialScore value={compat.overall} size={160} sublabel="compatibility" testId="compat-overall" />
              <div className="text-xs text-zinc-500 mt-3">out of 100</div>
            </div>

            <div className="divider my-6" />

            <div className="space-y-3" data-testid="compat-breakdown">
              {Object.entries(compat.breakdown).map(([k, v]) => (
                <div key={k}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-zinc-300">{LABEL[k]}</span>
                    <span className="font-mono text-zinc-100">{v}</span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${v}%`, background: 'linear-gradient(90deg,#8A2BE2,#C4B5FD)' }} />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => setOpen(true)}
              data-testid="propose-collab-btn"
              className="btn-primary w-full mt-6 inline-flex items-center justify-center gap-2"
            >
              <MessageSquare size={16} /> Propose collaboration
            </button>
          </div>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg border-white/10" style={{ background: '#12121A' }} data-testid="propose-modal">
          <DialogHeader>
            <DialogTitle className="font-display text-xl">Propose a collab with Sarah</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-zinc-500">Idea</label>
              <input
                value={proposal.idea}
                onChange={e => setProposal({ ...proposal, idea: e.target.value })}
                placeholder="e.g. 48-hour AI agent build-off"
                data-testid="proposal-idea-input"
                className="w-full mt-2 bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-zinc-500">Personal message</label>
              <textarea
                value={proposal.message}
                onChange={e => setProposal({ ...proposal, message: e.target.value })}
                rows={4}
                placeholder="Hi Sarah — loved your last agent breakdown. I've been running a similar experiment on the business side..."
                data-testid="proposal-message-input"
                className="w-full mt-2 bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500 resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="btn-ghost">Cancel</button>
            <button onClick={submit} disabled={sending || !proposal.message} data-testid="proposal-send-btn" className="btn-primary inline-flex items-center gap-2 disabled:opacity-50">
              <Send size={14} /> {sending ? 'Sending…' : 'Send proposal'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
