import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, ClipboardCheck, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';

function message(err, fallback) {
  return err?.response?.data?.error?.message || fallback;
}

export default function ProjectPlan({ project, onActivityChanged }) {
  const [requirements, setRequirements] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const req = await api.get(`/v1/projects/${project.id}/planning-requirements`);
      setRequirements(req.data);
      try {
        const p = await api.get(`/v1/projects/${project.id}/creative-plan`);
        setPlan(p.data);
      } catch (err) {
        if (err?.response?.status !== 404) setError(message(err, 'Could not load creative plan.'));
      }
    } catch (err) {
      setError(message(err, 'Could not load planning requirements.'));
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => { load(); }, [load]);

  const grouped = useMemo(() => {
    const out = {};
    for (const item of requirements?.requirements || []) {
      if (!out[item.category]) out[item.category] = [];
      out[item.category].push(item);
    }
    return out;
  }, [requirements]);

  const generate = async () => {
    setGenerating(true); setError(null);
    try {
      const r = await api.post(`/v1/projects/${project.id}/creative-plan/generate`);
      setPlan(r.data);
      if (onActivityChanged) onActivityChanged();
      toast(`Creative plan v${r.data.version} generated.`);
    } catch (err) {
      setError(message(err, 'Could not build the creative plan.'));
    } finally { setGenerating(false); }
  };

  const approve = async () => {
    if (!plan) return;
    setApproving(true);
    try {
      const r = await api.put(`/v1/projects/${project.id}/creative-plan/${plan.id}/approve`);
      setPlan(r.data);
      if (onActivityChanged) onActivityChanged();
      toast('Creative plan approved.');
    } catch (err) {
      toast(message(err, 'Could not approve creative plan.'));
    } finally { setApproving(false); }
  };

  if (loading) return <div className="text-sm text-zinc-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading planning system…</div>;

  if (requirements && !requirements.supported) {
    return (
      <div className="card-surface p-10 text-center">
        <Sparkles className="mx-auto mb-3 text-violet-400" size={22} />
        <div className="font-display text-xl">Deep planning for this format is coming next.</div>
        <div className="text-sm text-zinc-500 mt-2">{requirements.message}</div>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="creative-plan-tab">
      <section className="card-surface p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">Creative specification</div>
            <h2 className="font-display text-xl md:text-2xl font-semibold">Plan the Reel before generating it.</h2>
            <p className="text-sm text-zinc-500 mt-1 max-w-2xl">CreatorOS owns the production schema. AI fills the plan; it does not decide what a Reel plan should contain.</p>
          </div>
          <button onClick={generate} disabled={generating}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                  data-testid="creative-plan-generate">
            {generating ? <Loader2 size={14} className="animate-spin" /> : (plan ? <RefreshCw size={14} /> : <Sparkles size={14} />)}
            {generating ? 'Building plan…' : (plan ? 'Build new version' : 'Build creative plan')}
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] px-4 py-3 text-sm text-amber-200 flex gap-2">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      {!plan && (
        <section className="card-surface p-5">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-4">What CreatorOS will resolve</div>
          <div className="space-y-5">
            {Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <div className="text-sm font-medium capitalize mb-2">{category}</div>
                <div className="grid md:grid-cols-2 gap-2">
                  {items.map((item) => (
                    <div key={item.key} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                      <div className="text-sm text-zinc-200">{item.label}</div>
                      <div className="text-xs text-zinc-500 mt-1">{item.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {plan && (
        <>
          <section className="card-surface p-5" data-testid="creative-plan-summary">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-zinc-500">Plan v{plan.version} · {plan.duration_seconds}s · {plan.status}</div>
                <h3 className="font-display text-xl font-semibold mt-1">{plan.audience_takeaway}</h3>
              </div>
              <button onClick={approve} disabled={approving || plan.status === 'approved'}
                      className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
                      data-testid="creative-plan-approve">
                {approving ? <Loader2 size={14} className="animate-spin" /> : <ClipboardCheck size={14} />}
                {plan.status === 'approved' ? 'Approved' : 'Approve plan'}
              </button>
            </div>
            <div className="grid md:grid-cols-2 gap-4 mt-5">
              <Meta label="Objective" value={plan.objective} />
              <Meta label="Hook strategy" value={plan.hook_strategy} />
              <Meta label="Narrative arc" value={plan.narrative_arc} />
              <Meta label="Tone" value={plan.tone} />
              <Meta label="CTA / payoff" value={plan.cta} />
            </div>
          </section>

          <section className="card-surface overflow-hidden" data-testid="creative-plan-beats">
            <div className="p-5 border-b border-white/10">
              <div className="text-xs uppercase tracking-widest text-zinc-500">Beat-by-beat production plan</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-left text-sm">
                <thead className="text-[10px] uppercase tracking-widest text-zinc-500 border-b border-white/10">
                  <tr><th className="p-3">Time</th><th className="p-3">Purpose</th><th className="p-3">Spoken / audio</th><th className="p-3">Visual</th><th className="p-3">Shot / framing</th><th className="p-3">Text</th><th className="p-3">Assets / evidence</th></tr>
                </thead>
                <tbody>
                  {(plan.beats || []).map((beat, i) => (
                    <tr key={`${beat.start_second}-${i}`} className="border-b border-white/5 align-top">
                      <td className="p-3 text-violet-300 whitespace-nowrap">{beat.start_second}–{beat.end_second}s</td>
                      <td className="p-3 text-zinc-200">{beat.purpose}</td>
                      <td className="p-3 text-zinc-300 whitespace-pre-wrap">{beat.spoken_audio}</td>
                      <td className="p-3 text-zinc-300">{beat.visual}</td>
                      <td className="p-3 text-zinc-300">{beat.shot_framing}</td>
                      <td className="p-3 text-zinc-300">{beat.on_screen_text || '—'}</td>
                      <td className="p-3 text-xs text-zinc-400">
                        {[...(beat.assets || []), ...(beat.evidence_requirements || [])].map((x) => <div key={x} className="mb-1">• {x}</div>)}
                        {!beat.assets?.length && !beat.evidence_requirements?.length ? '—' : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid md:grid-cols-3 gap-4">
            <ListCard title="Required assets" items={plan.required_assets} />
            <ListCard title="Research required" items={plan.research_requirements} warning />
            <ListCard title="Unresolved decisions" items={plan.unresolved_decisions} warning />
          </div>
        </>
      )}
    </div>
  );
}

function Meta({ label, value }) {
  if (!value) return null;
  return <div><div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div><div className="text-sm text-zinc-200 leading-relaxed">{value}</div></div>;
}

function ListCard({ title, items = [], warning = false }) {
  return (
    <div className="card-surface p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-zinc-500 mb-3">
        {warning && items.length ? <AlertTriangle size={12} className="text-amber-300" /> : <Check size={12} className="text-emerald-300" />}
        {title}
      </div>
      {items.length ? <ul className="space-y-2 text-sm text-zinc-300">{items.map((x) => <li key={x}>• {x}</li>)}</ul> : <div className="text-sm text-zinc-500">Nothing outstanding.</div>}
    </div>
  );
}
