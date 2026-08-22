import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import BookmarkButton from '../components/BookmarkButton';
import RadialScore from '../components/RadialScore';
import { BookmarkX } from 'lucide-react';
import { useShortlist } from '../lib/shortlist';

export default function Shortlist() {
  const [items, setItems] = useState(null);
  const { isSaved, count } = useShortlist();

  const load = async () => {
    const r = await api.get('/shortlist');
    setItems(r.data);
  };
  useEffect(() => { load(); }, []);
  // Re-sync visible list when the shared shortlist cache changes (e.g. unbookmark on this page)
  useEffect(() => {
    if (items) setItems(prev => prev.filter(it => isSaved(it.opportunity_id)));
    // eslint-disable-next-line
  }, [count]);

  return (
    <div data-testid="shortlist-page">
      <div className="mb-8">
        <div className="chip chip-accent mb-3">Your shortlist</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Saved for later.</h1>
        <p className="mt-3 text-zinc-400 max-w-xl">Opportunities you bookmarked — ready to hand to your editor or come back to.</p>
      </div>

      {items === null ? (
        <div className="text-zinc-500">Loading…</div>
      ) : items.length === 0 ? (
        <div className="card-surface p-10 text-center">
          <BookmarkX className="mx-auto mb-3 text-zinc-500" size={28} />
          <div className="text-zinc-300 font-display text-lg">Nothing saved yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Tap the bookmark on any opportunity to save it here.</div>
          <Link to="/app" className="btn-primary inline-block mt-6" data-testid="shortlist-browse-cta">Browse feed</Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((it, i) => {
            const o = it.opportunity;
            return (
              <motion.div key={it.opportunity_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <div className="card-surface p-6 card-hover relative" data-testid={`saved-${it.opportunity_id}`}>
                  <div className="absolute top-4 right-4">
                    <BookmarkButton oppId={it.opportunity_id} />
                  </div>
                  <Link to={`/app/opportunity/${it.opportunity_id}`} className="block">
                    <div className="flex items-start gap-5">
                      <RadialScore value={o.score} size={80} sublabel="score" />
                      <div className="flex-1 pr-8">
                        <div className="chip mb-2">{o.trend.name} · {o.trend.stage}</div>
                        <h3 className="font-display text-lg font-semibold leading-snug">{o.title}</h3>
                        <div className="text-xs text-zinc-500 mt-3">Saved {new Date(it.saved_at).toLocaleDateString()}</div>
                      </div>
                    </div>
                  </Link>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
