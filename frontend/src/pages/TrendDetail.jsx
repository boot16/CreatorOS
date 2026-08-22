import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import Sparkline from '../components/Sparkline';
import { TrendingUp, ArrowRight } from 'lucide-react';

const stageColor = (s) => ({
  Emerging: '#10B981', Accelerating: '#8A2BE2', Mainstream: '#F59E0B', Saturated: '#EF4444',
}[s] || '#8A2BE2');

export default function TrendDetail() {
  const { id } = useParams();
  const [t, setT] = useState(null);

  useEffect(() => {
    setT(null);
    api.get(`/trends/${id}`).then(r => setT(r.data));
  }, [id]);

  if (!t) return <div className="text-zinc-500">Loading trend…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="trend-detail">
      <Link to="/app/trends" className="text-xs text-zinc-500 hover:text-white">← Back to radar</Link>

      <div className="mt-6 grid lg:grid-cols-[1fr_320px] gap-8">
        <div>
          <div className="chip mb-4" style={{ borderColor: stageColor(t.stage) + '55', color: stageColor(t.stage) }}>
            {t.category} · {t.stage}
          </div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">{t.name}</h1>

          <div className="mt-6 grid grid-cols-3 gap-3">
            <div className="card-surface p-4">
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">Momentum</div>
              <div className="font-display text-3xl font-semibold mt-1" style={{ color: t.momentum > 0 ? '#10B981' : '#EF4444' }}>
                {t.momentum > 0 ? '+' : ''}{t.momentum}%
              </div>
              <Sparkline data={t.sparkline} width={120} height={30} positive={t.momentum > 0} />
            </div>
            <div className="card-surface p-4">
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">Volume</div>
              <div className="font-display text-3xl font-semibold mt-1">{t.volume}</div>
              <div className="text-xs text-zinc-500 mt-2">indexed search + creation</div>
            </div>
            <div className="card-surface p-4">
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">Saturation</div>
              <div className="font-display text-3xl font-semibold mt-1" style={{ color: t.saturation < 40 ? '#10B981' : t.saturation < 70 ? '#F59E0B' : '#EF4444' }}>
                {t.saturation}
              </div>
              <div className="text-xs text-zinc-500 mt-2">creator competition</div>
            </div>
          </div>

          {/* Explanation */}
          <div className="card-surface p-6 mt-6">
            <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Why it's trending</h3>
            <p className="text-zinc-200 leading-relaxed">{t.explanation?.why}</p>
            <div className="divider my-5" />
            <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Who's driving it</div>
            <p className="text-sm text-zinc-300">{t.explanation?.audience}</p>
          </div>

          <div className="card-surface p-6 mt-4">
            <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Related topics</h3>
            <div className="flex flex-wrap gap-2">
              {(t.explanation?.related || []).map((r, i) => (
                <span key={i} className="chip chip-accent">{r}</span>
              ))}
            </div>
          </div>
        </div>

        <div>
          {t.linked_opportunity_id ? (
            <div className="card-surface p-6 sticky top-24">
              <div className="text-[10px] uppercase tracking-widest text-violet-300">Your opportunity</div>
              <div className="font-display font-semibold text-lg mt-2 mb-4">This trend maps directly to a scored opportunity for Alex.</div>
              <Link to={`/app/opportunity/${t.linked_opportunity_id}`} data-testid="linked-opp-cta" className="btn-primary w-full inline-flex items-center justify-center gap-2">
                See the opportunity <ArrowRight size={16} />
              </Link>
            </div>
          ) : (
            <div className="card-surface p-6 text-sm text-zinc-400">
              No direct opportunity yet — this trend is being watched.
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
