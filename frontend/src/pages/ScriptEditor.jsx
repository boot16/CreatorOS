import React, { useEffect, useState, useRef } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import { Save, Wand2, Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';

const QUICK_REFINEMENTS = [
  'Make the hook 2x stronger — more specific, tighter',
  'Add sharper transitions between beats',
  'Cut 20% — tighten every line',
  'Rewrite in a more casual, first-person tone',
];

export default function ScriptEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const [s, setS] = useState(null);
  const [body, setBody] = useState('');
  const [saving, setSaving] = useState(false);
  const [refining, setRefining] = useState(false);
  const [instruction, setInstruction] = useState('');
  const dirty = useRef(false);

  useEffect(() => {
    api.get(`/scripts/${id}`).then(r => { setS(r.data); setBody(r.data.body); });
  }, [id]);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/scripts/${id}`, { body });
      dirty.current = false;
      toast.success('Saved');
    } catch { toast.error('Save failed'); }
    setSaving(false);
  };

  const refine = async (text) => {
    const inst = (text ?? instruction).trim();
    if (!inst) return;
    setRefining(true);
    try {
      const r = await api.post(`/scripts/${id}/refine`, { instruction: inst });
      setBody(r.data.body);
      setInstruction('');
      dirty.current = false;
      toast.success('Refined');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Refine failed'); }
    setRefining(false);
  };

  if (!s) return <div className="text-zinc-500">Loading…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="script-editor">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <Link to="/app/scripts" className="text-xs text-zinc-500 hover:text-white">← All scripts</Link>
          <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight mt-2 line-clamp-1">{s.title}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { navigator.clipboard.writeText(body); toast('Copied'); }}
            className="btn-ghost inline-flex items-center gap-2"
            data-testid="script-copy-btn"
          ><Copy size={14} /> Copy</button>
          <button
            onClick={save}
            disabled={saving || refining}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
            data-testid="script-save-btn"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-6">
        <div className="card-surface p-4" style={refining ? { opacity: 0.6 } : {}}>
          <textarea
            value={body}
            onChange={(e) => { setBody(e.target.value); dirty.current = true; }}
            disabled={refining}
            data-testid="script-body"
            className="w-full h-[640px] bg-transparent text-zinc-100 text-sm leading-relaxed font-mono resize-none focus:outline-none whitespace-pre-wrap"
          />
        </div>

        <div>
          <div className="card-surface p-5">
            <div className="flex items-center gap-2 mb-4">
              <Wand2 size={14} className="text-violet-300" />
              <div className="text-[10px] uppercase tracking-widest text-violet-300">Refine with AI</div>
            </div>
            <textarea
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              disabled={refining}
              rows={3}
              data-testid="refine-input"
              placeholder="e.g. Punch up the hook, add a callback to my last video, cut 20%…"
              className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500 resize-none disabled:opacity-50"
            />
            <button
              onClick={() => refine()}
              disabled={refining || !instruction.trim()}
              data-testid="refine-btn"
              className="btn-primary w-full mt-3 inline-flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {refining ? <><Loader2 size={14} className="animate-spin" /> Rewriting…</> : <><Wand2 size={14} /> Rewrite script</>}
            </button>
            <div className="divider my-5" />
            <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-3">Quick refinements</div>
            <div className="space-y-2">
              {QUICK_REFINEMENTS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => refine(q)}
                  disabled={refining}
                  data-testid={`quick-refine-${i}`}
                  className="w-full text-left text-xs text-zinc-300 p-2 rounded-lg border border-white/5 hover:border-violet-500/40 hover:bg-white/[0.02] transition-colors disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
