import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api, DEMO_CREATOR_ID } from '../lib/api';
import RadialScore from '../components/RadialScore';
import Sparkline from '../components/Sparkline';
import BookmarkButton from '../components/BookmarkButton';
import { TrendingUp, ArrowUpRight } from 'lucide-react';

const stageColor = (s) => ({
  Emerging: '#10B981', Accelerating: '#8A2BE2', Mainstream: '#F59E0B', Saturated: '#EF4444',
}[s] || '#8A2BE2');

export default function OpportunityFeed() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/creators/${DEMO_CREATOR_ID}/opportunities`).then(r => {
      setItems(r.data.sort((a, b) => b.score - a.score));
      setLoading(false);
    });
  }, []);

  return (
    <div data-testid="opportunity-feed">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="chip chip-accent mb-3">Opportunity feed</div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Your next move.</h1>
          <p className="mt-3 text-zinc-400 max-w-xl">Ranked by fit with your DNA, cross-referenced against live trends. Every score is explainable.</p>
        </div>
        <div className="chip">Sorted by score</div>
      </div>

      {loading ? (
        <div className="text-zinc-500">Loading opportunities…</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((o, i) => (
            <motion.div key={o.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
              <div className="card-surface p-6 card-hover relative">
                <div className="absolute top-4 right-4">
                  <BookmarkButton oppId={o.id} />
                </div>
                <Link to={`/app/opportunity/${o.id}`} data-testid={`opp-card-${o.id}`} className="block">
                  <div className="flex items-start gap-5">
                    <RadialScore value={o.score} size={92} sublabel="score" testId={`opp-score-${o.id}`} />
                    <div className="flex-1 min-w-0 pr-8">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="chip" style={{ borderColor: stageColor(o.trend.stage) + '55', color: stageColor(o.trend.stage) }}>
                          {o.trend.name} · {o.trend.stage}
                        </span>
                        <span className="chip">{o.format}</span>
                      </div>
                      <h3 className="font-display text-lg font-semibold leading-snug">{o.title}</h3>
                      <div className="mt-4 flex items-center justify-between">
                        <div className="flex items-center gap-3 text-xs text-zinc-400">
                          <span className="flex items-center gap-1">
                            <TrendingUp size={13} className={o.trend.momentum > 0 ? 'text-emerald-400' : 'text-red-400'} />
                            {o.trend.momentum > 0 ? '+' : ''}{o.trend.momentum}%
                          </span>
                          <Sparkline data={o.trend.sparkline} width={72} height={22} positive={o.trend.momentum > 0} />
                        </div>
                        <ArrowUpRight size={18} className="text-zinc-500" />
                      </div>
                    </div>
                  </div>
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
