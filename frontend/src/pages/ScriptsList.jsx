import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import { FileText, Plus, Trash2, Clock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function ScriptsList() {
  const [items, setItems] = useState(null);

  const load = async () => {
    const r = await api.get('/scripts');
    setItems(r.data);
  };
  useEffect(() => { load(); }, []);

  const del = async (id) => {
    if (!confirm('Delete this script?')) return;
    await api.delete(`/scripts/${id}`);
    load();
    toast('Deleted');
  };

  return (
    <div data-testid="scripts-list">
      <div className="mb-8">
        <div className="chip chip-accent mb-3">Script drafts</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Your scripts.</h1>
        <p className="mt-3 text-zinc-400 max-w-xl">First drafts written in your voice — refine turn-by-turn with the assistant.</p>
      </div>

      {items === null ? (
        <div className="text-zinc-500">Loading…</div>
      ) : items.length === 0 ? (
        <div className="card-surface p-10 text-center">
          <FileText className="mx-auto mb-3 text-zinc-500" size={28} />
          <div className="text-zinc-300 font-display text-lg">No drafts yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Open any opportunity → Idea Lab → "Turn into script".</div>
          <Link to="/app" className="btn-primary inline-block mt-6" data-testid="scripts-browse-cta">Browse opportunities</Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((s, i) => (
            <motion.div key={s.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <div className="card-surface p-6 card-hover relative" data-testid={`script-item-${s.id}`}>
                <Link to={`/app/scripts/${s.id}`} className="block pr-10">
                  <div className="chip mb-3"><FileText size={11} /> Draft</div>
                  <h3 className="font-display text-lg font-semibold leading-snug line-clamp-2">{s.title}</h3>
                  <div className="text-xs text-zinc-500 mt-3 flex items-center gap-1">
                    <Clock size={12} /> Updated {new Date(s.updated_at).toLocaleString()}
                  </div>
                </Link>
                <button onClick={() => del(s.id)} className="absolute top-4 right-4 p-2 rounded-full text-zinc-500 hover:text-red-400 hover:bg-white/5">
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
