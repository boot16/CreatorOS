import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Loader2, RefreshCw, Sparkles, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';

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

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/v1/projects/${projectId}/creative-directions`);
      setDirections(r.data.directions || []);
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
          <button
            onClick={generate}
            disabled={generating}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
            data-testid="creative-directions-generate-v2"
          >
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
          <div className="text-[10px] uppercase tracking-widest text-emerald-300 mb-2">Selected direction</div>
          <h3 className="font-display text-xl font-semibold">{selected.title}</h3>
          <p className="text-sm text-zinc-300 mt-2">{selected.premise}</p>
          <div className="grid md:grid-cols-2 gap-4 mt-4">
            <Meta label="Angle" value={selected.angle} />
            <Meta label="Audience promise" value={selected.audience_promise} />
            <Meta label="Creative treatment" value={selected.creative_treatment} />
            <Meta label="Narrative shape" value={selected.narrative_shape} />
          </div>
        </section>
      )}

      {latestBatch.length > 0 ? (
        <div className="grid xl:grid-cols-3 gap-4" data-testid="creative-direction-options-v2">
          {latestBatch.map((direction) => (
            <article
              key={direction.id}
              className={`card-surface p-5 flex flex-col gap-4 ${direction.status === 'rejected' ? 'opacity-45' : ''}`}
              data-testid={`creative-direction-v2-${direction.id}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="chip chip-accent">{direction.narrative_shape || 'Direction'}</span>
                <span className="text-[10px] uppercase tracking-widest text-zinc-600">{direction.status}</span>
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

              {!!direction.risks?.length && (
                <ListBlock label="Risks / things to solve" items={direction.risks} />
              )}
              {!!direction.unresolved_questions?.length && (
                <ListBlock label="Unresolved" items={direction.unresolved_questions} />
              )}

              <div className="mt-auto pt-2 flex gap-2">
                <button
                  onClick={() => select(direction)}
                  disabled={busyId === direction.id || direction.status === 'selected'}
                  className="btn-primary flex-1 inline-flex items-center justify-center gap-2 disabled:opacity-50"
                  data-testid={`creative-direction-select-v2-${direction.id}`}
                >
                  {busyId === direction.id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                  {direction.status === 'selected' ? 'Selected' : 'Choose'}
                </button>
                <button
                  onClick={() => reject(direction)}
                  disabled={busyId === direction.id || direction.status === 'rejected'}
                  className="btn-ghost px-3 inline-flex items-center justify-center disabled:opacity-40"
                  title="Reject this direction"
                  data-testid={`creative-direction-reject-v2-${direction.id}`}
                >
                  <X size={14} />
                </button>
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
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
      <ul className="space-y-1 text-xs text-zinc-400">
        {items.map((item, i) => <li key={`${item}-${i}`}>• {item}</li>)}
      </ul>
    </div>
  );
}
