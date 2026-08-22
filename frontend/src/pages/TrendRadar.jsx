import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import Sparkline from '../components/Sparkline';

const CATEGORIES = ['All', 'AI', 'Business', 'Tech', 'Productivity'];

const stageColor = (s) => ({
  Emerging: '#10B981', Accelerating: '#8A2BE2', Mainstream: '#F59E0B', Saturated: '#EF4444',
}[s] || '#8A2BE2');

export default function TrendRadar() {
  const [category, setCategory] = useState('All');
  const [trends, setTrends] = useState([]);

  useEffect(() => {
    api.get('/trends', { params: category === 'All' ? {} : { category } }).then(r => setTrends(r.data));
  }, [category]);

  return (
    <div data-testid="trend-radar">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="chip chip-accent mb-3">Trend Radar</div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">What your niche is about to care about.</h1>
          <p className="mt-3 text-zinc-400">Filtered to trends where your DNA still has runway.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {CATEGORIES.map(c => (
            <button
              key={c}
              data-testid={`filter-${c.toLowerCase()}`}
              onClick={() => setCategory(c)}
              className="px-4 py-2 rounded-full text-sm border transition-colors"
              style={{
                background: category === c ? 'rgba(138,43,226,0.14)' : 'rgba(255,255,255,0.03)',
                borderColor: category === c ? 'rgba(138,43,226,0.5)' : 'rgba(255,255,255,0.08)',
                color: category === c ? '#E9D5FF' : '#A1A1AA',
              }}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Bubble radar */}
      <div className="card-surface p-6 mb-6 relative overflow-hidden">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-4">Momentum × Volume</div>
        <div className="relative h-[360px]" data-testid="trend-bubble-map">
          {/* Axis lines */}
          <div className="absolute inset-0 opacity-30"
               style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
                        backgroundSize: '10% 25%' }} />
          <div className="absolute left-0 bottom-0 text-[10px] text-zinc-600 uppercase tracking-widest">Momentum →</div>
          <div className="absolute left-0 top-0 -rotate-90 origin-top-left translate-y-full text-[10px] text-zinc-600 uppercase tracking-widest">Volume →</div>

          {trends.map((t, i) => {
            const x = Math.max(2, Math.min(95, (Math.max(-30, t.momentum) + 30) / 300 * 100));
            const y = Math.max(4, Math.min(90, 100 - t.volume));
            const size = 32 + (t.volume / 100) * 60;
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${x}%`, top: `${y}%` }}
              >
                <Link
                  to={`/app/trends/${t.id}`}
                  data-testid={`bubble-${t.id}`}
                  className="group block"
                  title={t.name}
                >
                  <div
                    className="rounded-full flex items-center justify-center border transition-transform group-hover:scale-110"
                    style={{
                      width: size, height: size,
                      background: `radial-gradient(circle at 30% 30%, ${stageColor(t.stage)}55, ${stageColor(t.stage)}10)`,
                      borderColor: stageColor(t.stage) + '80',
                      boxShadow: `0 0 24px -4px ${stageColor(t.stage)}66`,
                    }}
                  >
                    <span className="font-mono text-[10px] text-white">{t.momentum > 0 ? '+' : ''}{t.momentum}</span>
                  </div>
                  <div className="text-center text-[11px] text-zinc-300 mt-2 whitespace-nowrap">{t.name}</div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div className="grid md:grid-cols-2 gap-3">
        {trends.map(t => (
          <Link key={t.id} to={`/app/trends/${t.id}`} data-testid={`trend-list-${t.id}`} className="card-surface p-5 card-hover">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="chip mb-2" style={{ borderColor: stageColor(t.stage) + '55', color: stageColor(t.stage) }}>{t.stage}</div>
                <h3 className="font-display font-semibold text-lg">{t.name}</h3>
                <div className="text-xs text-zinc-500 mt-1">{t.category} · saturation {t.saturation}</div>
              </div>
              <div className="text-right">
                <div className="font-display font-semibold text-xl" style={{ color: t.momentum > 0 ? '#10B981' : '#EF4444' }}>
                  {t.momentum > 0 ? '+' : ''}{t.momentum}%
                </div>
                <Sparkline data={t.sparkline} width={80} height={24} positive={t.momentum > 0} />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
