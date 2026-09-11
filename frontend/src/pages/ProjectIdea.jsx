import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { Textarea } from '../components/ui/textarea';

function errorMessage(err, fallback) {
  return err?.response?.data?.error?.message || fallback;
}

const FIELDS = [
  ['subject', 'Subject', 'What the idea is actually about'],
  ['creator_perspective', 'Your perspective', 'The point of view CreatorOS heard in your idea'],
  ['core_claim', 'Core belief / claim', 'The central thought the content may need to express or prove'],
  ['intent', 'Intent', 'What this piece is trying to accomplish'],
  ['target_audience', 'Likely audience', 'Who this appears most relevant to'],
  ['desired_effect', 'Desired effect', 'What should change in the viewer after they see it'],
];

function originLabel(origin) {
  if (origin === 'confirmed') return 'Confirmed by you';
  if (origin === 'creator_provided') return 'From your input';
  return 'CreatorOS inference';
}

function originClass(origin) {
  if (origin === 'confirmed') return 'text-emerald-300 border-emerald-400/20 bg-emerald-400/5';
  if (origin === 'creator_provided') return 'text-sky-300 border-sky-400/20 bg-sky-400/5';
  return 'text-amber-200 border-amber-400/20 bg-amber-400/5';
}

function cleanLines(value) {
  return value
    .split('\n')
    .map((x) => x.replace(/^[-•]\s*/, '').trim())
    .filter(Boolean);
}

export default function ProjectIdea({ project, onActivityChanged }) {
  const projectId = project.id;
  const [understanding, setUnderstanding] = useState(null);
  const [rawIdea, setRawIdea] = useState(project.brief?.topic || project.objective || '');
  const [draft, setDraft] = useState({});
  const [assumptionsText, setAssumptionsText] = useState('');
  const [questionsText, setQuestionsText] = useState('');
  const [unknownsText, setUnknownsText] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const hydrate = useCallback((item) => {
    setUnderstanding(item);
    setRawIdea(item.raw_idea || '');
    const next = {};
    for (const [key] of FIELDS) next[key] = item[key]?.value || '';
    setDraft(next);
    setAssumptionsText((item.assumptions || []).map((x) => `- ${x}`).join('\n'));
    setQuestionsText((item.open_questions || []).map((x) => `- ${x}`).join('\n'));
    setUnknownsText((item.material_unknowns || []).map((x) => `- ${x}`).join('\n'));
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get(`/v1/projects/${projectId}/idea-understanding`)
      .then((r) => { if (alive) hydrate(r.data); })
      .catch((err) => {
        if (!alive) return;
        if (err?.response?.status !== 404) setError(errorMessage(err, 'Could not load idea understanding.'));
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [projectId, hydrate]);

  const generate = async () => {
    if (rawIdea.trim().length < 3) {
      toast('Write a little more about the idea first.');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const r = await api.post(`/v1/projects/${projectId}/idea-understanding/generate`, {
        raw_idea: rawIdea.trim(),
      });
      hydrate(r.data);
      if (onActivityChanged) onActivityChanged();
      toast('CreatorOS mapped the idea. Review what it understood.');
    } catch (err) {
      setError(errorMessage(err, 'Could not understand the idea. Your text is still here.'));
    } finally {
      setGenerating(false);
    }
  };

  const changedFields = useMemo(() => {
    if (!understanding) return [];
    return FIELDS
      .map(([key]) => key)
      .filter((key) => (draft[key] || '') !== (understanding[key]?.value || ''));
  }, [draft, understanding]);

  const save = async () => {
    if (!understanding) return;
    setSaving(true);
    setError(null);
    const body = {};
    for (const [key] of FIELDS) body[key] = draft[key] || '';
    body.assumptions = cleanLines(assumptionsText);
    body.open_questions = cleanLines(questionsText);
    body.material_unknowns = cleanLines(unknownsText);
    try {
      const r = await api.patch(`/v1/projects/${projectId}/idea-understanding`, body);
      hydrate(r.data);
      if (onActivityChanged) onActivityChanged();
      toast('Understanding confirmed.');
    } catch (err) {
      setError(errorMessage(err, 'Could not save your corrections.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading idea…</div>;
  }

  return (
    <div className="space-y-5" data-testid="idea-understanding-tab">
      <section className="card-surface p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">Start with the thought in your head</div>
            <h2 className="font-display text-xl md:text-2xl font-semibold">What do you want to make something about?</h2>
            <p className="text-sm text-zinc-500 mt-1 max-w-2xl">
              It can be rough. CreatorOS should understand the thought before it starts writing for you.
            </p>
          </div>
          {understanding && <span className="text-xs text-zinc-500">Understanding v{understanding.version}</span>}
        </div>

        <Textarea
          value={rawIdea}
          onChange={(e) => setRawIdea(e.target.value)}
          rows={5}
          maxLength={10000}
          placeholder="Example: Everyone talks about AI saving time, but I think the bigger shift is that one person can now attempt things that used to need a team..."
          className="bg-black/20 border-white/10 text-base leading-relaxed"
          data-testid="idea-raw-input"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            onClick={generate}
            disabled={generating || rawIdea.trim().length < 3}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
            data-testid="idea-understand-btn"
          >
            {generating ? <Loader2 size={14} className="animate-spin" /> : (understanding ? <RefreshCw size={14} /> : <Sparkles size={14} />)}
            {generating ? 'Understanding…' : (understanding ? 'Re-understand idea' : 'Understand this idea')}
          </button>
          <span className="text-xs text-zinc-500">No script or direction is generated at this stage.</span>
        </div>
      </section>

      {error && (
        <div className="card-surface px-4 py-3 text-sm text-red-300 flex items-center gap-2" data-testid="idea-error">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {understanding && (
        <>
          <section className="card-surface p-5 md:p-6" data-testid="idea-understanding-review">
            <div className="mb-5">
              <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">What CreatorOS understood</div>
              <h3 className="font-display text-xl font-semibold">Correct the meaning, not the wording.</h3>
              <p className="text-sm text-zinc-500 mt-1">
                Inferences stay labelled as inferences until you confirm them. You can edit anything that does not sound like you.
              </p>
            </div>

            <div className="grid xl:grid-cols-2 gap-4">
              {FIELDS.map(([key, label, help]) => {
                const field = understanding[key] || {};
                return (
                  <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <div>
                        <div className="text-xs uppercase tracking-widest text-zinc-300">{label}</div>
                        <div className="text-[11px] text-zinc-600 mt-0.5">{help}</div>
                      </div>
                      <span className={`text-[10px] border rounded-full px-2 py-1 whitespace-nowrap ${originClass(field.origin)}`}>
                        {originLabel(field.origin)}
                      </span>
                    </div>
                    <Textarea
                      value={draft[key] || ''}
                      onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                      rows={key === 'creator_perspective' || key === 'core_claim' ? 3 : 2}
                      className="bg-black/20 border-white/10 text-sm"
                      data-testid={`idea-field-${key}`}
                    />
                  </div>
                );
              })}
            </div>
          </section>

          {(unknownsText || questionsText || assumptionsText) && (
            <section className="grid lg:grid-cols-3 gap-4">
              <ListEditor
                label="Material unknowns"
                help="Only things that could change the direction or execution."
                value={unknownsText}
                onChange={setUnknownsText}
                testId="idea-material-unknowns"
              />
              <ListEditor
                label="Useful questions"
                help="Questions worth resolving later, not a required questionnaire."
                value={questionsText}
                onChange={setQuestionsText}
                testId="idea-open-questions"
              />
              <ListEditor
                label="Assumptions"
                help="What CreatorOS had to assume from the idea or project context."
                value={assumptionsText}
                onChange={setAssumptionsText}
                testId="idea-assumptions"
              />
            </section>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={save}
              disabled={saving}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
              data-testid="idea-confirm-btn"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {saving ? 'Saving…' : 'Confirm understanding'}
            </button>
            <span className="text-xs text-zinc-500">
              {changedFields.length ? `${changedFields.length} meaning field${changedFields.length === 1 ? '' : 's'} changed` : 'You can confirm as-is or correct anything first.'}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function ListEditor({ label, help, value, onChange, testId }) {
  return (
    <div className="card-surface p-4">
      <div className="text-xs uppercase tracking-widest text-zinc-300">{label}</div>
      <div className="text-[11px] text-zinc-600 mt-1 mb-3">{help}</div>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={5}
        className="bg-black/20 border-white/10 text-sm"
        data-testid={testId}
      />
    </div>
  );
}
