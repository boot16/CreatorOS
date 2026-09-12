import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { Textarea } from '../components/ui/textarea';

function errorMessage(err, fallback) {
  return err?.response?.data?.error?.message || fallback;
}

function valueOf(field) { return field?.value || ''; }

export default function ProjectIdea({ project, onActivityChanged }) {
  const [foundation, setFoundation] = useState(null);
  const [message, setMessage] = useState(project.brief?.topic || project.objective || '');
  const [nextQuestion, setNextQuestion] = useState(null);
  const [mode, setMode] = useState(null);
  const [canIdeate, setCanIdeate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    api.get(`/v1/projects/${project.id}/foundation`)
      .then((r) => { if (alive) setFoundation(r.data.foundation); })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [project.id]);

  const submit = async () => {
    if (message.trim().length < 2) return;
    setWorking(true); setError(null);
    try {
      const r = await api.post(`/v1/projects/${project.id}/foundation/understand`, { message: message.trim() });
      setFoundation(r.data.foundation);
      setNextQuestion(r.data.next_question || null);
      setMode(r.data.starting_mode);
      setCanIdeate(Boolean(r.data.can_ideate_now));
      setMessage('');
      onActivityChanged?.();
      if (r.data.next_question) toast('CreatorOS found the one thing worth resolving next.');
      else toast('Project context updated.');
    } catch (err) {
      setError(errorMessage(err, 'Could not update the project. Your text is still here.'));
    } finally { setWorking(false); }
  };

  if (loading) return <div className="text-sm text-zinc-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading project context…</div>;

  return (
    <div className="space-y-5" data-testid="ideation-workspace">
      <section className="card-surface p-6 md:p-8">
        <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">Ideation</div>
        <h2 className="font-display text-2xl md:text-3xl font-semibold">What are you trying to create?</h2>
        <p className="text-sm text-zinc-500 mt-2 max-w-2xl">Start anywhere. Bring an idea, ask CreatorOS to find one, describe a project, or tell it what you need to finish. You do not need to fill out a brief.</p>

        {!foundation && (
          <div className="grid sm:grid-cols-3 gap-3 mt-6 mb-5">
            <Starter title="I have an idea" text="Develop a thought I already have" onClick={() => setMessage('I have an idea: ')} />
            <Starter title="Help me find ideas" text="I know the project, not the content" onClick={() => setMessage('Help me find ideas for ')} />
            <Starter title="I need to make something" text="Start from a goal or opportunity" onClick={() => setMessage('I need to create ')} />
          </div>
        )}

        {nextQuestion && (
          <div className="mt-6 mb-4 rounded-2xl border border-violet-400/20 bg-violet-400/[0.05] p-5" data-testid="foundation-next-question">
            <div className="text-[11px] uppercase tracking-widest text-violet-300 mb-2">One thing would materially improve the work</div>
            <div className="text-lg font-medium">{nextQuestion}</div>
          </div>
        )}

        <Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} maxLength={10000}
          placeholder={nextQuestion ? 'Answer in your own words…' : 'Example: I’m starting an Instagram page for Mediq and I want help deciding what the first piece of content should be.'}
          className="mt-5 bg-black/20 border-white/10 text-base leading-relaxed" data-testid="foundation-input" />
        <div className="mt-3 flex items-center gap-3">
          <button onClick={submit} disabled={working || message.trim().length < 2} className="btn-primary inline-flex items-center gap-2 disabled:opacity-60" data-testid="foundation-submit">
            {working ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
            {working ? 'Thinking…' : (nextQuestion ? 'Continue' : foundation ? 'Update project context' : 'Start')}
          </button>
          {mode && <span className="text-xs text-zinc-500">CreatorOS recognized this as: {mode.replace('_', ' ')}</span>}
        </div>
      </section>

      {error && <div className="card-surface px-4 py-3 text-sm text-red-300 flex items-center gap-2"><AlertTriangle size={14} /> {error}</div>}

      {foundation && (
        <section className="card-surface p-6" data-testid="project-foundation-summary">
          <div className="flex items-start justify-between gap-4 mb-5">
            <div>
              <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">Project foundation</div>
              <h3 className="font-display text-xl font-semibold">CreatorOS is keeping the context. You keep creating.</h3>
              <p className="text-sm text-zinc-500 mt-1">This updates as decisions are made. You should not have to repeat the same context later.</p>
            </div>
            <span className="text-xs text-zinc-600">v{foundation.version}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <Context label="Vision" field={foundation.vision} />
            <Context label="Goal" field={foundation.goal} />
            <Context label="Context" field={foundation.context} />
            <Context label="Audience" field={foundation.audience} />
            {valueOf(foundation.creator_perspective) && <Context label="Your perspective" field={foundation.creator_perspective} />}
            <Context label="Platform / format" field={foundation.platform_format} />
          </div>
          {foundation.material_unknowns?.length > 0 && (
            <div className="mt-4 text-sm text-zinc-400"><span className="text-zinc-200">Still unresolved:</span> {foundation.material_unknowns.join(' · ')}</div>
          )}
          {canIdeate && !nextQuestion && (
            <div className="mt-5 flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 size={15} /> Enough context to develop useful creative possibilities.</div>
          )}
        </section>
      )}
    </div>
  );
}

function Starter({ title, text, onClick }) {
  return <button onClick={onClick} className="text-left rounded-2xl border border-white/10 bg-white/[0.02] p-4 hover:border-violet-400/30 transition-colors"><Sparkles size={15} className="text-violet-300 mb-3" /><div className="font-medium text-sm">{title}</div><div className="text-xs text-zinc-500 mt-1">{text}</div></button>;
}

function Context({ label, field }) {
  const value = valueOf(field);
  if (!value) return null;
  return <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4"><div className="flex items-center justify-between gap-2"><div className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</div><div className="text-[10px] text-zinc-600">{field?.origin === 'confirmed' ? 'confirmed' : 'working context'}</div></div><div className="text-sm text-zinc-200 mt-2 leading-relaxed">{value}</div></div>;
}
