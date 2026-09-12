import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, GitMerge, Loader2, RefreshCw, ShieldCheck, Sparkles, Wand2, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { Textarea } from '../components/ui/textarea';

function errorMessage(err, fallback) {
  return err?.response?.data?.error?.message || fallback;
}

export default function ProjectDirection({ project, onActivityChanged, onProjectChanged }) {
  const projectId = project.id;
  const [directions, setDirections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [refineInstruction, setRefineInstruction] = useState('');
  const [readiness, setReadiness] = useState(null);
  const [assessing, setAssessing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/v1/projects/${projectId}/creative-directions`);
      const items = r.data.directions || [];
      setDirections(items);
      const selected = items.find((d) => d.status === 'selected');
      if (selected) {
        try {
          const rr = await api.get(`/v1/projects/${projectId}/direction-readiness`);
          setReadiness(rr.data);
        } catch (err) {
          if (err?.response?.status !== 404) setReadiness(null);
        }
      }
    } catch (err) {
      setError(errorMessage(err, 'Could not load creative directions.'));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const latestBatch = useMemo(() => {
    if (!directions.length) return [];
    const latest = directions[directions.length - 1]?.batch_id;
    return directions.filter((d) => d.batch_id === latest);
  }, [directions]);

  const selected = useMemo(
    () => directions.find((d) => d.status === 'selected') || null,
    [directions]
  );

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const r = await api.post(`/v1/projects/${projectId}/creative-directions/generate`);
      const fresh = r.data.directions || [];
      setDirections((prev) => [...prev, ...fresh]);
      if (onActivityChanged) onActivityChanged();
      toast('Three distinct directions developed.');
    } catch (err) {
      setError(errorMessage(err, 'Could not develop directions.'));
    } finally {
      setGenerating(false);
    }
  };

  const select = async (direction) => {
    setBusyId(direction.id);
    try {
      const r = await api.put(`/v1/projects/${projectId}/creative-directions/${direction.id}/select`);
      setDirections((prev) => prev.map((d) => ({
        ...d,
        status: d.id === direction.id ? 'selected' : (d.status === 'selected' ? 'proposed' : d.status),
      })));
      setReadiness(null);
      if (onActivityChanged) onActivityChanged();
      if (onProjectChanged) onProjectChanged();
      toast(`Selected: ${r.data.title}`);
    } catch (err) {
      toast(errorMessage(err, 'Could not select direction.'));
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (direction) => {
    setBusyId(direction.id);
    try {
      await api.put(`/v1/projects/${projectId}/creative-directions/${direction.id}/reject`);
      setDirections((prev) => prev.map((d) => d.id === direction.id ? { ...d, status: 'rejected' } : d));
      if (onActivityChanged) onActivityChanged();
    } catch (err) {
      toast(errorMessage(err, 'Could not reject direction.'));
    } finally {
      setBusyId(null);
    }
  };

  const refine = async () => {
    if (!selected || refineInstruction.trim().length < 3) {
      toast('Tell CreatorOS what you want to change.');
      return;
    }
    setBusyId(selected.id);
    try {
      const r = await api.post(`/v1/projects/${projectId}/creative-directions/${selected.id}/refine`, {
        instruction: refineInstruction.trim(),
      });
      setDirections((prev) => [...prev, r.data]);
      setRefineInstruction('');
      if (onActivityChanged) onActivityChanged();
      toast('Refined direction created. Review it before choosing it.');
    } catch (err) {
      toast(errorMessage(err, 'Could not refine direction.'));
    } finally {
      setBusyId(null);
    }
  };

  const combine = async (secondary) => {
    if (!selected) return;
    setBusyId(secondary.id);
    try {
      const r = await api.post(`/v1/projects/${projectId}/creative-directions/${selected.id}/combine`, {
        secondary_direction_id: secondary.id,
      });
      setDirections((prev) => [...prev, r.data]);
      if (onActivityChanged) onActivityChanged();
      toast('Combined direction created. Review it before choosing it.');
    } catch (err) {
      toast(errorMessage(err, 'Could not combine directions.'));
    } finally {
      setBusyId(null);
    }
  };

  const assessReadiness = async () => {
    if (!selected) return;
    setAssessing(true);
    try {
      const r = await api.post(`/v1/projects/${projectId}/direction-readiness/assess`);
      setReadiness(r.data);
      if (onActivityChanged) onActivityChanged();
      toast(r.data.overall_status === 'ready' ? 'Direction is ready for planning.' : 'Readiness gaps identified.');
    } catch (err) {
      toast(errorMessage(err, 'Could not assess readiness.'));
    } finally {
      setAssessing(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading directions…</div>;
  }

  return (
    <div className="space-y-5" data-testid="creative-direction-v2-tab">
      <section className="card-surface p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">Develop the idea</div>
            <h2 className="font-display text-xl md:text-2xl font-semibold">Choose how this idea should become content.</h2>
            <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
              These are different creative treatments, not three versions of the same hook.
            </p>
          </div>
          <button onClick={generate} disabled={generating}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                  data-testid="creative-directions-generate-v2">
            {generating ? <Loader2 size={14} className="animate-spin" /> : (directions.length ? <RefreshCw size={14} /> : <Sparkles size={14} />)}
            {generating ? 'Developing…' : (directions.length ? 'Develop new directions' : 'Develop directions')}
          </button>
        </div>
      </section>

      {error && (
        <div className="card-surface px-4 py-3 text-sm text-amber-200 flex items-start gap-2" data-testid="creative-direction-v2-error">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {selected && (
        <section className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.04] p-5" data-testid="creative-direction-selected-v2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-emerald-300 mb-2">Selected direction · revision {selected.revision || 1}</div>
              <h3 className="font-display text-xl font-semibold">{selected.title}</h3>
              <p className="text-sm text-zinc-300 mt-2">{selected.premise}</p>
            </div>
            <button onClick={assessReadiness} disabled={assessing}
                    className="btn-ghost inline-flex items-center gap-2 disabled:opacity-60"
                    data-testid="direction-readiness-assess">
              {assessing ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              {assessing ? 'Assessing…' : 'Assess readiness'}
            </button>
          </div>
          <div className="grid md:grid-cols-2 gap-4 mt-4">
            <Meta label="Angle" value={selected.angle} />
            <Meta label="Audience promise" value={selected.audience_promise} />
            <Meta label="Creative treatment" value={selected.creative_treatment} />
            <Meta label="Narrative shape" value={selected.narrative_shape} />
          </div>

          <div className="mt-5 pt-5 border-t border-white/10">
            <div className="text-xs uppercase tracking-widest text-zinc-500 mb-2">Refine this direction</div>
            <Textarea
              value={refineInstruction}
              onChange={(e) => setRefineInstruction(e.target.value)}
              placeholder="Example: keep the contrarian argument, but make it more visual and use a concrete before/after example."
              rows={3}
              maxLength={3000}
              className="bg-black/20 border-white/10"
              data-testid="direction-refine-instruction"
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-xs text-zinc-500">Creates a new revision so the current direction is not overwritten.</span>
              <button onClick={refine} disabled={busyId === selected.id || refineInstruction.trim().length < 3}
                      className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
                      data-testid="direction-refine-submit">
                {busyId === selected.id ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                Refine
              </button>
            </div>
          </div>
        </section>
      )}

      {readiness && selected && readiness.direction_id === selected.id && (
        <ReadinessPanel readiness={readiness} />
      )}

      {latestBatch.length > 0 ? (
        <div className="grid xl:grid-cols-3 gap-4" data-testid="creative-direction-options-v2">
          {latestBatch.map((direction) => (
            <article key={direction.id}
                     className={`card-surface p-5 flex flex-col gap-4 ${direction.status === 'rejected' ? 'opacity-45' : ''}`}
                     data-testid={`creative-direction-v2-${direction.id}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="chip chip-accent">{direction.narrative_shape || 'Direction'}</span>
                <span className="text-[10px] uppercase tracking-widest text-zinc-600">{direction.status} · r{direction.revision || 1}</span>
              </div>
              <div>
                <h3 className="font-display text-xl font-semibold leading-snug">{direction.title}</h3>
                <p className="text-sm text-zinc-400 mt-2 leading-relaxed">{direction.premise}</p>
              </div>
              <Meta label="Angle" value={direction.angle} />
              <Meta label="Audience promise" value={direction.audience_promise} />
              <Meta label="Creative treatment" value={direction.creative_treatment} />
              <Meta label="Format fit" value={direction.format_fit} />
              <Meta label="Why this direction" value={direction.why_this_direction} />
              {!!direction.risks?.length && <ListBlock label="Risks / things to solve" items={direction.risks} />}
              {!!direction.unresolved_questions?.length && <ListBlock label="Unresolved" items={direction.unresolved_questions} />}

              <div className="mt-auto pt-2 space-y-2">
                <div className="flex gap-2">
                  <button onClick={() => select(direction)}
                          disabled={busyId === direction.id || direction.status === 'selected'}
                          className="btn-primary flex-1 inline-flex items-center justify-center gap-2 disabled:opacity-50"
                          data-testid={`creative-direction-select-v2-${direction.id}`}>
                    {busyId === direction.id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    {direction.status === 'selected' ? 'Selected' : 'Choose'}
                  </button>
                  <button onClick={() => reject(direction)}
                          disabled={busyId === direction.id || direction.status === 'rejected'}
                          className="btn-ghost px-3 inline-flex items-center justify-center disabled:opacity-40"
                          title="Reject this direction"
                          data-testid={`creative-direction-reject-v2-${direction.id}`}>
                    <X size={14} />
                  </button>
                </div>
                {selected && selected.id !== direction.id && direction.status !== 'rejected' && (
                  <button onClick={() => combine(direction)} disabled={busyId === direction.id}
                          className="btn-ghost w-full inline-flex items-center justify-center gap-2 text-xs disabled:opacity-50"
                          data-testid={`creative-direction-combine-v2-${direction.id}`}>
                    {busyId === direction.id ? <Loader2 size={13} className="animate-spin" /> : <GitMerge size={13} />}
                    Combine with selected
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="card-surface p-10 text-center">
          <Sparkles className="mx-auto mb-3 text-violet-400" size={22} />
          <div className="font-display text-lg">No creative directions yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Confirm the idea first, then develop distinct ways to express it.</div>
        </div>
      )}
    </div>
  );
}

function ReadinessPanel({ readiness }) {
  const ready = readiness.overall_status === 'ready';
  return (
    <section className={`rounded-2xl border p-5 ${ready ? 'border-emerald-400/20 bg-emerald-400/[0.03]' : 'border-amber-400/20 bg-amber-400/[0.03]'}`}
             data-testid="direction-readiness-panel">
      <div className="flex items-center gap-2 mb-4">
        {ready ? <ShieldCheck size={16} className="text-emerald-300" /> : <AlertTriangle size={16} className="text-amber-300" />}
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500">Direction readiness</div>
          <div className="font-display text-lg font-semibold">{ready ? 'Ready for detailed planning' : 'Resolve the material gaps first'}</div>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {(readiness.criteria || []).map((item) => (
          <div key={item.key} className="rounded-xl border border-white/5 bg-black/10 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-medium capitalize">{item.key.replaceAll('_', ' ')}</div>
              <span className={`text-[10px] uppercase tracking-widest ${item.status === 'ready' ? 'text-emerald-300' : 'text-amber-300'}`}>{item.status.replace('_', ' ')}</span>
            </div>
            <div className="text-xs text-zinc-400 mt-1 leading-relaxed">{item.note}</div>
            {item.evidence_needed && <div className="text-[10px] text-violet-300 mt-2 uppercase tracking-widest">Evidence needed</div>}
          </div>
        ))}
      </div>
      {!!readiness.blocking_questions?.length && <ListBlock label="Questions worth resolving" items={readiness.blocking_questions} />}
      {!!readiness.research_needs?.length && <ListBlock label="Research needed" items={readiness.research_needs} />}
      {!!readiness.planning_notes?.length && <ListBlock label="Planning notes" items={readiness.planning_notes} />}
    </section>
  );
}

function Meta({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
      <div className="text-sm text-zinc-200 leading-relaxed">{value}</div>
    </div>
  );
}

function ListBlock({ label, items }) {
  return (
    <div className="mt-3">
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
      <ul className="space-y-1 text-xs text-zinc-400">
        {items.map((item, i) => <li key={`${item}-${i}`}>• {item}</li>)}
      </ul>
    </div>
  );
}
