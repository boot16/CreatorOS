import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import RadialScore from '../components/RadialScore';
import Sparkline from '../components/Sparkline';
import HandoffMenu from '../components/HandoffMenu';
import { ChevronDown, Sparkles, TrendingUp, Send } from 'lucide-react';

const WEIGHTS = {
  TrendFit: 0.25, CreatorFit: 0.25, HistoricalFormatFit: 0.20,
  AudienceFit: 0.10, Freshness: 0.10, Saturation: 0.10,
};
const LABELS = {
  TrendFit: 'Trend fit', CreatorFit: 'Creator fit', HistoricalFormatFit: 'Historical format fit',
  AudienceFit: 'Audience fit', Freshness: 'Freshness', Saturation: 'Un-saturation',
};

export default function OpportunityDetail() {
  const { id } = useParams();
  const [o, setO] = useState(null);
  const [open, setOpen] = useState(true);
  const [handoff, setHandoff] = useState(false);

  useEffect(() => {
    setO(null);
    api.get(`/opportunities/${id}`).then(r => setO(r.data));
  }, [id]);

  if (!o) return <div className="text-zinc-500">Loading…</div>;

  const rows = Object.entries(o.sub_scores).map(([k, v]) => {
    const displayed = k === 'Saturation' ? 100 - v : v;
    const contrib = (WEIGHTS[k] * displayed).toFixed(1);
    return { key: k, raw: v, displayed, contrib };
  });

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="opportunity-detail">
      <Link to="/app" className="text-xs text-zinc-500 hover:text-white">← Back to feed</Link>

      <div className="mt-6 grid lg:grid-cols-[1fr_320px] gap-8">
        <div>
          <div className="chip chip-accent mb-4">Opportunity</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight leading-tight">{o.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-zinc-400">
            <span className="chip">{o.format}</span>
            <span className="chip">{o.trend.name} · {o.trend.stage}</span>
            <span className="flex items-center gap-1">
              <TrendingUp size={13} className={o.trend.momentum > 0 ? 'text-emerald-400' : 'text-red-400'} />
              {o.trend.momentum > 0 ? '+' : ''}{o.trend.momentum}% momentum
            </span>
            <Sparkline data={o.trend.sparkline} width={80} height={22} positive={o.trend.momentum > 0} />
          </div>

          {/* Why this fits */}
          <div className="card-surface p-6 mt-8">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles size={14} className="text-violet-300" />
              <h3 className="font-display text-base font-semibold uppercase tracking-widest">Why this fits you, right now</h3>
            </div>
            <ul className="space-y-3">
              {(o.why_bullets || []).map((b, i) => (
                <li key={i} className="flex gap-3 text-sm text-zinc-200" data-testid={`why-bullet-${i}`}>
                  <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0 bg-violet-400" />
                  {b}
                </li>
              ))}
            </ul>
          </div>

          {/* Breakdown */}
          <div className="card-surface mt-4">
            <button
              onClick={() => setOpen(!open)}
              data-testid="how-calculated-toggle"
              className="w-full flex items-center justify-between p-6"
            >
              <div>
                <div className="text-[10px] uppercase tracking-widest text-violet-300">Under the hood</div>
                <div className="font-display text-base font-semibold mt-1">How was this calculated?</div>
              </div>
              <ChevronDown className={`transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>
            <AnimatePresence>
              {open && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="px-6 pb-6 border-t border-white/5 pt-6 space-y-3" data-testid="score-breakdown">
                    {rows.map(r => (
                      <div key={r.key} className="grid grid-cols-[1fr_auto_auto] items-center gap-4">
                        <div>
                          <div className="text-sm text-zinc-200">{LABELS[r.key]}</div>
                          <div className="h-1.5 mt-2 bg-white/5 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${r.displayed}%`, background: 'linear-gradient(90deg,#8A2BE2,#C4B5FD)' }} />
                          </div>
                        </div>
                        <div className="font-mono text-xs text-zinc-500 w-16 text-right">×{WEIGHTS[r.key]}</div>
                        <div className="font-display font-semibold text-white w-16 text-right">{r.displayed}</div>
                      </div>
                    ))}
                    <div className="divider my-4" />
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-400 uppercase tracking-widest text-[10px]">Weighted sum</span>
                      <span className="font-display text-2xl font-semibold">{o.score}</span>
                    </div>
                    <div className="text-xs text-zinc-500 mt-3 leading-relaxed">
                      Formula: 0.25×TrendFit + 0.25×CreatorFit + 0.20×FormatFit + 0.10×AudienceFit + 0.10×Freshness + 0.10×(100−Saturation)
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div>
          <div className="card-surface p-6 sticky top-24">
            <RadialScore value={o.score} size={140} sublabel="opportunity" />
            <div className="text-center mt-3 text-zinc-500 text-xs">out of 100</div>

            <div className="divider my-6" />
            <Link to={`/app/idea/${o.id}`} data-testid="open-idea-lab" className="btn-primary w-full inline-flex items-center justify-center gap-2">
              <Sparkles size={16} /> Open Idea Lab
            </Link>
            <button onClick={() => setHandoff(true)} data-testid="send-editor-btn" className="btn-ghost w-full mt-3 inline-flex items-center justify-center gap-2">
              <Send size={14} /> Send to editor
            </button>
            <Link to={`/app/trends/${o.trend_id}`} className="btn-ghost w-full text-center mt-3 inline-block">
              See trend detail
            </Link>
          </div>
        </div>
      </div>

      <HandoffMenu oppId={o.id} open={handoff} onOpenChange={setHandoff} />
    </motion.div>
  );
}
