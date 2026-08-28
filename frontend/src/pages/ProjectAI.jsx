import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import {
  Loader2, Sparkles, Plus, Trash2, ExternalLink, Wand2, Zap, Search,
  Check, X, MessageSquare, Send, RotateCcw, AlertTriangle,
} from 'lucide-react';
import { api } from '../lib/api';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from '../components/ui/alert-dialog';

// -------- utility hook --------
function useDebouncedEffect(fn, deps, delay) {
  const timer = useRef(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(fn, delay);
    return () => timer.current && clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function errorMessage(err, fallback = 'Something went wrong.') {
  return err?.response?.data?.error?.message || fallback;
}

// ==============================================================
// RESEARCH TAB
// ==============================================================
export function ResearchTab({ project, onProjectChanged, onCreativeObjectsChanged }) {
  const projectId = project.id;
  const [research, setResearch] = useState(null); // CreativeObject | null
  const [sources, setSources] = useState([]);
  const [question, setQuestion] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [objs, srcs] = await Promise.all([
        api.get(`/v1/projects/${projectId}/creative-objects`),
        api.get(`/v1/projects/${projectId}/sources`),
      ]);
      setResearch(objs.data.find((o) => o.type === 'research') || null);
      setSources(srcs.data);
    } catch {
      /* handled per action */
    }
  }, [projectId]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const run = async () => {
    if (!question.trim()) { toast('Enter a research question first.'); return; }
    setRunning(true); setError(null);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/research`, {
        question: question.trim(),
      });
      setResearch(r.data.creative_object);
      if (onCreativeObjectsChanged) onCreativeObjectsChanged();
      if (onProjectChanged) onProjectChanged();
      toast('Research brief saved.');
    } catch (err) {
      setError(errorMessage(err, 'Research failed — your notes are safe.'));
    } finally {
      setRunning(false);
    }
  };

  const onEdit = async (content) => {
    if (!research) return;
    try {
      const r = await api.patch(`/v1/projects/${projectId}/creative-objects/${research.id}`, { content });
      setResearch(r.data);
    } catch {
      toast('Save failed');
    }
  };

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-6" data-testid="research-tab">
      <div className="space-y-5">
        <div className="card-surface p-5">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">Research question</Label>
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What do you want the AI to look into for this project?"
            rows={2}
            maxLength={2000}
            className="mt-2 bg-black/20 border-white/10"
            data-testid="research-question-input"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={run}
              disabled={running || !question.trim()}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
              data-testid="research-run-btn"
            >
              {running ? <Loader2 className="animate-spin" size={14} /> : <Search size={14} />}
              {running ? 'Researching…' : 'Run research'}
            </button>
            <span className="text-xs text-zinc-500">
              Grounded in this project's brief + sources. Never invents URLs.
            </span>
          </div>
          {error && (
            <div className="mt-3 flex items-center gap-2 text-xs text-red-300" data-testid="research-error">
              <AlertTriangle size={12} /> {error}
              <button className="underline" onClick={run}>Retry</button>
            </div>
          )}
        </div>

        {research ? (
          <ResearchEditor object={research} onCommit={onEdit} />
        ) : (
          <div className="card-surface p-10 text-center" data-testid="research-empty">
            <Sparkles className="mx-auto mb-3 text-violet-400" size={22} />
            <div className="font-display text-lg">No research yet.</div>
            <div className="text-sm text-zinc-500 mt-1">
              Add sources on the right, then run research above.
            </div>
          </div>
        )}
      </div>

      <SourcesPanel projectId={projectId} sources={sources} onChange={setSources} />
    </div>
  );
}

function ResearchEditor({ object, onCommit }) {
  const [content, setContent] = useState(object.content || '');
  const [state, setState] = useState('saved');
  const initial = useRef(object.content || '');
  useEffect(() => { setContent(object.content || ''); initial.current = object.content || ''; setState('saved'); }, [object.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useDebouncedEffect(() => {
    if (content === initial.current) return;
    setState('saving');
    onCommit(content).then(() => { initial.current = content; setState('saved'); }).catch(() => setState('dirty'));
  }, [content], 700);

  return (
    <div className="card-surface p-5" data-testid="research-editor">
      <div className="flex items-center justify-between mb-3">
        <div className="chip chip-accent">Research brief</div>
        <div className="text-xs text-zinc-500 flex items-center gap-1">
          {state === 'saving' && <><Loader2 size={11} className="animate-spin" /> Saving</>}
          {state === 'saved' && <><Check size={11} className="text-emerald-400" /> Saved</>}
          {state === 'dirty' && <>Editing…</>}
        </div>
      </div>
      <Textarea
        value={content}
        onChange={(e) => { setContent(e.target.value); setState('dirty'); }}
        rows={16}
        maxLength={100000}
        className="bg-black/20 border-white/10 font-mono text-sm"
        data-testid="research-content-input"
      />
    </div>
  );
}

function SourcesPanel({ projectId, sources, onChange }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [type, setType] = useState('url');
  const [saving, setSaving] = useState(false);

  const add = async (e) => {
    e.preventDefault();
    if (!title.trim()) { toast('Add a title'); return; }
    if (type === 'url' && !url.trim()) { toast('Add a URL'); return; }
    setSaving(true);
    try {
      const body = { title: title.trim(), source_type: type };
      if (type === 'url') body.url = url.trim();
      body.content = text.trim();
      const r = await api.post(`/v1/projects/${projectId}/sources`, body);
      onChange([...sources, r.data]);
      setTitle(''); setUrl(''); setText(''); setType('url'); setOpen(false);
      toast('Source added');
    } catch (err) {
      toast(errorMessage(err, 'Could not add source'));
    } finally { setSaving(false); }
  };

  const del = async (id) => {
    try {
      await api.delete(`/v1/projects/${projectId}/sources/${id}`);
      onChange(sources.filter((s) => s.id !== id));
    } catch { toast('Delete failed'); }
  };

  return (
    <aside className="card-surface p-5 h-max sticky top-24" data-testid="sources-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs uppercase tracking-widest text-zinc-500">Sources</div>
        <button
          onClick={() => setOpen(true)}
          className="btn-ghost !py-1 !px-3 text-xs inline-flex items-center gap-1"
          data-testid="add-source-btn"
        >
          <Plus size={12} /> Add
        </button>
      </div>
      {sources.length === 0 ? (
        <div className="text-sm text-zinc-500">No sources yet. Add URLs or paste text.</div>
      ) : (
        <ul className="space-y-3" data-testid="sources-list">
          {sources.map((s) => (
            <li key={s.id} className="text-sm border border-white/5 rounded-xl p-3 bg-white/[0.02]"
                data-testid={`source-item-${s.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{s.title}</div>
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-xs text-violet-300 hover:underline flex items-center gap-1 truncate">
                      <ExternalLink size={10} /> {s.url}
                    </a>
                  )}
                  {s.source_type === 'text' && s.content && (
                    <div className="text-xs text-zinc-500 mt-1 line-clamp-2">{s.content}</div>
                  )}
                </div>
                <button onClick={() => del(s.id)} className="p-1 rounded text-zinc-500 hover:text-red-400" data-testid={`source-delete-${s.id}`}>
                  <Trash2 size={12} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-white/10" style={{ background: '#12121A' }}>
          <DialogHeader>
            <DialogTitle>Add a source</DialogTitle>
            <DialogDescription className="text-zinc-400 text-sm">
              A URL you've read, or a chunk of text you want the AI to consider.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={add} className="space-y-4 pt-2">
            <div>
              <Label className="text-xs uppercase tracking-widest text-zinc-400">Type</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger className="mt-2 bg-black/20 border-white/10" data-testid="source-type-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="url">URL</SelectItem>
                  <SelectItem value="text">Pasted text</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-widest text-zinc-400">Title</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500}
                     className="mt-2 bg-black/20 border-white/10" data-testid="source-title-input" />
            </div>
            {type === 'url' && (
              <div>
                <Label className="text-xs uppercase tracking-widest text-zinc-400">URL</Label>
                <Input value={url} onChange={(e) => setUrl(e.target.value)} maxLength={2000}
                       placeholder="https://…"
                       className="mt-2 bg-black/20 border-white/10" data-testid="source-url-input" />
              </div>
            )}
            <div>
              <Label className="text-xs uppercase tracking-widest text-zinc-400">
                Content {type === 'text' ? '(pasted text)' : '(optional summary)'}
              </Label>
              <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} maxLength={20000}
                        className="mt-2 bg-black/20 border-white/10" data-testid="source-content-input" />
            </div>
            <DialogFooter>
              <button type="submit" disabled={saving}
                      className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                      data-testid="source-save-btn">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Save
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </aside>
  );
}

// ==============================================================
// DIRECTION TAB
// ==============================================================
export function DirectionTab({ project, onProjectChanged, onCreativeObjectsChanged }) {
  const projectId = project.id;
  const [selected, setSelected] = useState(null);   // CreativeObject | null
  const [options, setOptions] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    const r = await api.get(`/v1/projects/${projectId}/creative-objects`);
    setSelected(r.data.find((o) => o.type === 'direction') || null);
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setGenerating(true); setError(null); setOptions([]);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/directions`);
      setOptions(r.data.directions || []);
    } catch (err) {
      setError(errorMessage(err, 'Could not generate directions.'));
    } finally { setGenerating(false); }
  };

  const pick = async (d) => {
    try {
      const r = await api.put(`/v1/projects/${projectId}/ai/direction/selected`, d);
      setSelected(r.data);
      setOptions([]);
      if (onProjectChanged) onProjectChanged();
      if (onCreativeObjectsChanged) onCreativeObjectsChanged();
      toast('Direction saved.');
    } catch (err) {
      toast(errorMessage(err, 'Could not save direction'));
    }
  };

  const clearSelection = async () => {
    if (!selected) return;
    try {
      await api.delete(`/v1/projects/${projectId}/creative-objects/${selected.id}`);
      setSelected(null);
      if (onCreativeObjectsChanged) onCreativeObjectsChanged();
      toast('Cleared selection');
    } catch { toast('Could not clear'); }
  };

  return (
    <div className="space-y-5" data-testid="direction-tab">
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={generate} disabled={generating}
                className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                data-testid="directions-generate-btn">
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {generating ? 'Generating…' : (options.length || selected ? 'Regenerate options' : 'Generate 2-3 directions')}
        </button>
        <span className="text-xs text-zinc-500">
          Built from Brief + Research + Sources for this project.
        </span>
        {selected && (
          <button onClick={clearSelection} className="btn-ghost !py-1 !px-3 text-xs inline-flex items-center gap-1 ml-auto" data-testid="direction-clear-btn">
            <RotateCcw size={12} /> Clear selection
          </button>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-300 flex items-center gap-2" data-testid="directions-error">
          <AlertTriangle size={12} /> {error}
        </div>
      )}

      {selected && !options.length && (
        <div className="card-surface p-5" data-testid="direction-selected">
          <div className="flex items-center gap-2 mb-3">
            <span className="chip chip-accent">Selected direction</span>
          </div>
          <h3 className="font-display text-xl font-semibold">{selected.title}</h3>
          <pre className="text-sm text-zinc-300 mt-4 whitespace-pre-wrap font-sans">{selected.content}</pre>
        </div>
      )}

      {options.length > 0 && (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="direction-options">
          {options.map((d, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="card-surface p-5 flex flex-col gap-3" data-testid={`direction-option-${i}`}>
              <div className="chip chip-accent w-max">Option {i + 1}</div>
              <div>
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Angle</div>
                <div className="font-display text-lg leading-snug">{d.angle}</div>
              </div>
              <MetaLine label="Audience takeaway" value={d.audience_takeaway} />
              <MetaLine label="Format" value={d.format} />
              <MetaLine label="Tone" value={d.tone} />
              <MetaLine label="Why it works" value={d.why_it_works} />
              <button onClick={() => pick(d)}
                      className="btn-primary mt-auto inline-flex items-center justify-center gap-2"
                      data-testid={`direction-select-${i}`}>
                <Check size={14} /> Choose this
              </button>
            </motion.div>
          ))}
        </div>
      )}

      {!selected && !options.length && !generating && (
        <div className="card-surface p-10 text-center" data-testid="direction-empty">
          <Sparkles className="mx-auto mb-3 text-violet-400" size={22} />
          <div className="font-display text-lg">No direction chosen yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Generate options above, then pick or edit one.</div>
        </div>
      )}
    </div>
  );
}

function MetaLine({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
      <div className="text-sm text-zinc-200">{value}</div>
    </div>
  );
}

// ==============================================================
// CONTENT TAB (extended with AI generate + edit actions)
// ==============================================================

const CONTENT_TYPE_LABELS = {
  youtube_video: { outline: 'Generate outline', content: 'Generate script' },
  instagram_reel: { outline: 'Generate outline', content: 'Generate reel script' },
  instagram_post: { outline: 'Generate outline', content: 'Generate caption' },
  instagram_carousel: { outline: 'Generate outline', content: 'Generate carousel slides' },
};

const CREATIVE_TYPE_OPTIONS = [
  { value: 'notes', label: 'Notes' },
  { value: 'outline', label: 'Outline' },
  { value: 'script', label: 'Script' },
  { value: 'caption', label: 'Caption' },
  { value: 'carousel', label: 'Carousel' },
];

export function ContentTab({ project, onProjectChanged }) {
  const projectId = project.id;
  const [items, setItems] = useState(null);
  const [newType, setNewType] = useState('notes');
  const [generating, setGenerating] = useState(null); // 'outline' | 'content' | null
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    const r = await api.get(`/v1/projects/${projectId}/creative-objects`);
    setItems(r.data.filter((o) => !['research', 'direction'].includes(o.type)));
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const labels = CONTENT_TYPE_LABELS[project.content_type] || CONTENT_TYPE_LABELS.youtube_video;

  const genOutline = async () => {
    setGenerating('outline'); setError(null);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/outline`);
      setItems((prev) => {
        const others = (prev || []).filter((o) => o.type !== 'outline');
        return [r.data.creative_object, ...others];
      });
      if (onProjectChanged) onProjectChanged();
      toast('Outline generated.');
    } catch (err) {
      setError(errorMessage(err, 'Outline generation failed. Your drafts are safe.'));
    } finally { setGenerating(null); }
  };

  const genContent = async () => {
    setGenerating('content'); setError(null);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/content`);
      setItems((prev) => [r.data, ...(prev || [])]);
      if (onProjectChanged) onProjectChanged();
      toast('AI draft added.');
    } catch (err) {
      setError(errorMessage(err, 'Content generation failed. Your drafts are safe.'));
    } finally { setGenerating(null); }
  };

  const manualCreate = async () => {
    try {
      const r = await api.post(`/v1/projects/${projectId}/creative-objects`, {
        type: newType, title: '', content: '',
      });
      setItems((prev) => [...(prev || []), r.data]);
      toast('New draft added');
    } catch { toast('Could not create'); }
  };

  return (
    <div className="space-y-5" data-testid="content-tab">
      <div className="card-surface p-5">
        <div className="text-xs uppercase tracking-widest text-zinc-500 mb-3">AI generation</div>
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={genOutline} disabled={!!generating}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                  data-testid="ai-outline-btn">
            {generating === 'outline' ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {labels.outline}
          </button>
          <button onClick={genContent} disabled={!!generating}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
                  data-testid="ai-content-btn">
            {generating === 'content' ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
            {labels.content}
          </button>
          <span className="text-xs text-zinc-500">Uses Brief + Research + Selected direction.</span>
        </div>
        {error && (
          <div className="mt-3 flex items-center gap-2 text-xs text-red-300" data-testid="content-error">
            <AlertTriangle size={12} /> {error}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1"><p className="text-sm text-zinc-400">All drafts autosave.</p></div>
        <Select value={newType} onValueChange={setNewType}>
          <SelectTrigger className="w-40 bg-black/20 border-white/10" data-testid="new-object-type-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CREATIVE_TYPE_OPTIONS.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <button onClick={manualCreate} className="btn-primary inline-flex items-center gap-2 !py-2 !px-4 text-sm" data-testid="new-object-btn">
          <Plus size={14} /> Add manual
        </button>
      </div>

      {items === null ? (
        <div className="text-zinc-500 text-sm flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Loading drafts…</div>
      ) : items.length === 0 ? (
        <div className="card-surface p-10 text-center" data-testid="content-empty">
          <div className="font-display text-lg">No drafts yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Generate an outline or add a manual note.</div>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((o) => (
            <CreativeObjectEditor
              key={o.id}
              obj={o}
              projectId={projectId}
              onChanged={(u) => setItems((prev) => prev.map((x) => x.id === u.id ? u : x))}
              onDeleted={(id) => setItems((prev) => prev.filter((x) => x.id !== id))}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CreativeObjectEditor({ obj, projectId, onChanged, onDeleted }) {
  const [title, setTitle] = useState(obj.title || '');
  const [content, setContent] = useState(obj.content || '');
  const [saveState, setSaveState] = useState('saved');
  const initial = useRef({ title: obj.title || '', content: obj.content || '' });

  const [aiBusy, setAiBusy] = useState(null); // 'rewrite' | 'improve_hook' | 'critique' | null
  const [proposal, setProposal] = useState(null); // { action, proposal }
  const [critique, setCritique] = useState(null);
  const [rewriteOpen, setRewriteOpen] = useState(false);
  const [rewriteInstr, setRewriteInstr] = useState('');

  useEffect(() => {
    setTitle(obj.title || '');
    setContent(obj.content || '');
    initial.current = { title: obj.title || '', content: obj.content || '' };
    setSaveState('saved');
  }, [obj.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useDebouncedEffect(() => {
    if (title === initial.current.title && content === initial.current.content) return;
    (async () => {
      setSaveState('saving');
      try {
        const r = await api.patch(`/v1/projects/${projectId}/creative-objects/${obj.id}`, { title, content });
        initial.current = { title: r.data.title || '', content: r.data.content || '' };
        setSaveState('saved');
        onChanged(r.data);
      } catch { setSaveState('dirty'); toast('Save failed'); }
    })();
  }, [title, content], 700);

  const runAi = async (action, instruction = '') => {
    setAiBusy(action);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/edit`, {
        action, content, instruction: instruction || null,
      });
      if (action === 'critique') {
        setCritique(r.data.critique);
      } else {
        setProposal({ action, text: r.data.proposal });
      }
    } catch (err) {
      toast(errorMessage(err, 'AI action failed. Content unchanged.'));
    } finally { setAiBusy(null); }
  };

  const acceptProposal = async () => {
    if (!proposal) return;
    const newText = proposal.text;
    setContent(newText);
    setSaveState('dirty');
    setProposal(null);
    toast('AI edit applied. You can undo by editing.');
  };

  const del = async () => {
    try {
      await api.delete(`/v1/projects/${projectId}/creative-objects/${obj.id}`);
      onDeleted(obj.id);
      toast('Deleted');
    } catch { toast('Delete failed'); }
  };

  const badgeColor = obj.type === 'outline' ? 'chip-accent' :
                     obj.type === 'script' ? 'chip-accent' :
                     obj.type === 'caption' ? 'chip-accent' :
                     obj.type === 'carousel' ? 'chip-accent' : '';

  return (
    <div className="card-surface p-5" data-testid={`creative-object-${obj.id}`}>
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <span className={`chip ${badgeColor}`}>{obj.type}</span>
        <Input
          value={title}
          onChange={(e) => { setTitle(e.target.value); setSaveState('dirty'); }}
          placeholder="Untitled"
          className="bg-transparent border-0 focus-visible:ring-0 flex-1 font-display text-lg font-semibold px-0"
          data-testid={`creative-object-title-${obj.id}`}
        />
        <div className="text-xs text-zinc-500 flex items-center gap-1 min-w-[80px] justify-end">
          {saveState === 'saving' && <><Loader2 size={11} className="animate-spin" /> Saving</>}
          {saveState === 'saved' && <><Check size={11} className="text-emerald-400" /> Saved</>}
          {saveState === 'dirty' && <>Editing…</>}
        </div>
      </div>

      <Textarea
        value={content}
        onChange={(e) => { setContent(e.target.value); setSaveState('dirty'); }}
        placeholder="Start writing…"
        rows={10}
        maxLength={100000}
        data-testid={`creative-object-content-${obj.id}`}
        className="bg-black/20 border-white/10 font-mono text-sm"
      />

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setRewriteOpen(true)}
          disabled={!content.trim() || !!aiBusy}
          className="btn-ghost !py-1.5 !px-3 text-xs inline-flex items-center gap-1 disabled:opacity-50"
          data-testid={`ai-rewrite-btn-${obj.id}`}
        >
          <Wand2 size={12} /> Rewrite
        </button>
        <button
          onClick={() => runAi('improve_hook')}
          disabled={!content.trim() || !!aiBusy}
          className="btn-ghost !py-1.5 !px-3 text-xs inline-flex items-center gap-1 disabled:opacity-50"
          data-testid={`ai-improve-hook-btn-${obj.id}`}
        >
          {aiBusy === 'improve_hook' ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />} Improve hook
        </button>
        <button
          onClick={() => runAi('critique')}
          disabled={!content.trim() || !!aiBusy}
          className="btn-ghost !py-1.5 !px-3 text-xs inline-flex items-center gap-1 disabled:opacity-50"
          data-testid={`ai-critique-btn-${obj.id}`}
        >
          {aiBusy === 'critique' ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} Critique
        </button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button className="ml-auto p-2 rounded-full text-zinc-500 hover:text-red-400 hover:bg-white/5" data-testid={`creative-object-delete-${obj.id}`}>
              <Trash2 size={12} />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent className="border-white/10" style={{ background: '#12121A' }}>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this draft?</AlertDialogTitle>
              <AlertDialogDescription>This can't be undone.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={del} data-testid={`creative-object-confirm-delete-${obj.id}`}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {/* Rewrite instruction dialog */}
      <Dialog open={rewriteOpen} onOpenChange={setRewriteOpen}>
        <DialogContent className="border-white/10" style={{ background: '#12121A' }}>
          <DialogHeader>
            <DialogTitle>Rewrite this draft</DialogTitle>
            <DialogDescription className="text-zinc-400 text-sm">
              Tell the AI what to change. Your original stays until you accept.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={rewriteInstr}
            onChange={(e) => setRewriteInstr(e.target.value)}
            placeholder="e.g. Make it punchier, less generic, keep the same beats."
            rows={4}
            maxLength={2000}
            className="bg-black/20 border-white/10"
            data-testid={`rewrite-instruction-${obj.id}`}
          />
          <DialogFooter>
            <button
              onClick={() => { setRewriteOpen(false); runAi('rewrite', rewriteInstr || 'Rewrite for clarity and voice.'); setRewriteInstr(''); }}
              disabled={aiBusy === 'rewrite'}
              className="btn-primary inline-flex items-center gap-2"
              data-testid={`rewrite-submit-${obj.id}`}
            >
              {aiBusy === 'rewrite' ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />} Rewrite
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Proposal preview */}
      <AnimatePresence>
        {proposal && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-4 border border-violet-500/30 rounded-2xl p-4 bg-violet-500/5"
            data-testid={`proposal-${obj.id}`}
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="chip chip-accent">AI proposal — {proposal.action}</span>
              <span className="text-xs text-zinc-500">Preview. Not applied yet.</span>
            </div>
            <pre className="text-sm whitespace-pre-wrap font-mono text-zinc-100">{proposal.text}</pre>
            <div className="mt-3 flex items-center gap-2">
              <button onClick={acceptProposal} className="btn-primary inline-flex items-center gap-2 !py-1.5 !px-3 text-xs" data-testid={`proposal-accept-${obj.id}`}>
                <Check size={12} /> Accept & replace
              </button>
              <button onClick={() => setProposal(null)} className="btn-ghost inline-flex items-center gap-2 !py-1.5 !px-3 text-xs" data-testid={`proposal-discard-${obj.id}`}>
                <X size={12} /> Discard
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Critique */}
      <AnimatePresence>
        {critique && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-4 border border-white/10 rounded-2xl p-4 bg-white/[0.02]"
            data-testid={`critique-${obj.id}`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="chip chip-accent">Critique</span>
              <button onClick={() => setCritique(null)} className="text-zinc-500 hover:text-white">
                <X size={14} />
              </button>
            </div>
            <CritiqueList title="Strengths" items={critique.strengths} tone="text-emerald-300" />
            <CritiqueList title="Weaknesses" items={critique.weaknesses} tone="text-amber-300" />
            <CritiqueList title="Suggestions" items={critique.suggestions} tone="text-violet-300" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function CritiqueList({ title, items, tone }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-3">
      <div className={`text-[10px] uppercase tracking-widest mb-1.5 ${tone}`}>{title}</div>
      <ul className="text-sm text-zinc-200 list-disc pl-5 space-y-1">
        {items.map((s, i) => <li key={i}>{s}</li>)}
      </ul>
    </div>
  );
}

// ==============================================================
// PROJECT ASSISTANT
// ==============================================================
export function ProjectAssistant({ projectId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.get(`/v1/projects/${projectId}/ai/chat`).then((r) => setMessages(r.data)).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    const optimisticUser = { id: 'temp-' + Date.now(), role: 'user', content: text, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, optimisticUser]);
    setSending(true);
    try {
      const r = await api.post(`/v1/projects/${projectId}/ai/chat`, { message: text });
      setMessages((prev) => [...prev, r.data]);
    } catch (err) {
      setMessages((prev) => [...prev, {
        id: 'err-' + Date.now(), role: 'assistant',
        content: '(assistant temporarily unavailable — try again shortly.)',
        created_at: new Date().toISOString(),
      }]);
    } finally { setSending(false); }
  };

  return (
    <div className="card-surface flex flex-col h-[520px]" data-testid="project-assistant">
      <div className="p-4 border-b border-white/5 flex items-center gap-2">
        <MessageSquare size={14} className="text-violet-400" />
        <div className="text-xs uppercase tracking-widest text-zinc-400">Project assistant</div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="assistant-messages">
        {messages.length === 0 && (
          <div className="text-sm text-zinc-500 text-center pt-10">
            Ask about this project — angle, hook, gaps, direction, structure.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={m.id || i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              data-testid={`assistant-msg-${m.role}-${i}`}
              className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-violet-500/20 text-white border border-violet-500/30'
                  : 'bg-white/[0.03] text-zinc-100 border border-white/10'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start" data-testid="assistant-thinking">
            <div className="max-w-[85%] px-3 py-2 rounded-2xl text-sm bg-white/[0.03] border border-white/10 text-zinc-400">
              <Loader2 size={12} className="animate-spin inline mr-2" /> Thinking…
            </div>
          </div>
        )}
      </div>
      <div className="p-3 border-t border-white/5 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          disabled={sending}
          placeholder="Ask about this project…"
          data-testid="assistant-input"
          className="flex-1 bg-white/[0.03] border border-white/10 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-violet-500 disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          data-testid="assistant-send-btn"
          className="btn-primary !py-2 !px-4 inline-flex items-center gap-2 disabled:opacity-50"
        >
          {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
        </button>
      </div>
    </div>
  );
}
