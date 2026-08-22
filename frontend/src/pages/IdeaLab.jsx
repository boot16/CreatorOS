import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import { Sparkles, Copy, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function IdeaLab() {
  const { oppId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    api.post('/idea-lab', { opportunity_id: oppId })
      .then(r => setData(r.data))
      .catch(e => setErr(e?.response?.data?.detail || 'Generation failed'));
  }, [oppId]);

  const copy = (t) => { navigator.clipboard.writeText(t); toast('Copied'); };

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="idea-lab">
      <Link to={`/app/opportunity/${oppId}`} className="text-xs text-zinc-500 hover:text-white">← Back to opportunity</Link>

      <div className="mt-6">
        <div className="chip chip-accent mb-4"><Sparkles size={12} /> Idea Lab</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Generated with your DNA.</h1>
        <p className="mt-3 text-zinc-400 max-w-xl">A concept, four titles, three cold-open hooks, and a five-beat structure — grounded in Alex's voice.</p>
      </div>

      {!data && !err && (
        <div className="card-surface p-10 mt-8 flex items-center gap-3 text-zinc-400">
          <Loader2 className="animate-spin" size={18} /> Generating with Claude Sonnet 4.6 (~5-8s)…
        </div>
      )}
      {err && (
        <div className="card-surface p-6 mt-8 border-red-500/40 text-red-300">{err}</div>
      )}

      {data && (
        <div className="grid lg:grid-cols-3 gap-4 mt-8">
          {/* Concept */}
          <div className="card-surface p-6 lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-base font-semibold uppercase tracking-widest">Concept</h3>
              <button onClick={() => copy(data.concept)} className="text-zinc-500 hover:text-white"><Copy size={14} /></button>
            </div>
            <p className="text-zinc-100 leading-relaxed" data-testid="idea-concept">{data.concept}</p>
          </div>

          {/* Structure */}
          <div className="card-surface p-6">
            <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Video structure</h3>
            <ol className="space-y-3" data-testid="idea-structure">
              {(data.structure || []).map((s, i) => (
                <li key={i} className="flex gap-3">
                  <div className="w-6 h-6 shrink-0 rounded-full flex items-center justify-center text-xs font-mono bg-violet-500/15 text-violet-300">{i+1}</div>
                  <div className="text-sm text-zinc-200 leading-snug">{s}</div>
                </li>
              ))}
            </ol>
          </div>

          {/* Titles */}
          <div className="card-surface p-6 lg:col-span-2">
            <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Title options</h3>
            <div className="space-y-2" data-testid="idea-titles">
              {(data.titles || []).map((t, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/5 group">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-zinc-500 font-mono">0{i+1}</span>
                    <span className="text-zinc-100">{t}</span>
                  </div>
                  <button onClick={() => copy(t)} className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-white transition-opacity">
                    <Copy size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Hooks */}
          <div className="card-surface p-6">
            <h3 className="font-display text-base font-semibold uppercase tracking-widest mb-4">Cold-open hooks</h3>
            <div className="space-y-3" data-testid="idea-hooks">
              {(data.hooks || []).map((h, i) => (
                <div key={i} className="p-3 rounded-xl border-l-2 border-violet-500 bg-white/[0.02]">
                  <div className="text-[10px] uppercase tracking-widest text-violet-300 mb-1">Hook {i+1}</div>
                  <div className="text-sm text-zinc-200 italic">"{h}"</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
