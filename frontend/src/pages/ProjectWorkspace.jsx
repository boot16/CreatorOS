import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Save, Check, Loader2, Youtube, Instagram, Trash2, Plus,
  FileText, ListChecks, Sparkles, Rocket, Compass, ChevronRight, Clock,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from '../components/ui/alert-dialog';

const STATUSES = [
  { value: 'idea', label: 'Idea' },
  { value: 'researching', label: 'Researching' },
  { value: 'developing', label: 'Developing' },
  { value: 'writing', label: 'Writing' },
  { value: 'ready', label: 'Ready' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'discarded', label: 'Discarded' },
];

const CREATIVE_TYPES = [
  { value: 'notes', label: 'Notes' },
  { value: 'outline', label: 'Outline' },
  { value: 'script', label: 'Script' },
  { value: 'caption', label: 'Caption' },
  { value: 'carousel', label: 'Carousel' },
];

const BRIEF_FIELDS = [
  { key: 'topic', label: 'Topic / idea', placeholder: 'What is this piece really about?', textarea: true },
  { key: 'objective', label: 'Objective', placeholder: 'What should this achieve? (views, subs, leads, brand)', textarea: true },
  { key: 'target_audience', label: 'Target audience', placeholder: 'Who is this for, specifically?', textarea: true },
  { key: 'content_format', label: 'Content format', placeholder: 'Experiment, tutorial, listicle, story…', textarea: false },
  { key: 'takeaway', label: 'Viewer takeaway', placeholder: 'What should they walk away with?', textarea: true },
  { key: 'working_title', label: 'Working title', placeholder: 'The hook / headline you\'re aiming for', textarea: false },
];

function PlatformIcon({ platform, size = 14 }) {
  if (platform === 'youtube') return <Youtube size={size} className="text-red-400" />;
  return <Instagram size={size} className="text-pink-400" />;
}

/** Debounced autosave hook. */
function useDebouncedEffect(fn, deps, delay) {
  const timer = useRef(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(fn, delay);
    return () => timer.current && clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function BriefTab({ project, onSaved }) {
  const [brief, setBrief] = useState(project.brief || {});
  const [saveState, setSaveState] = useState('saved'); // saved | dirty | saving
  const initial = useRef(JSON.stringify(project.brief || {}));

  useEffect(() => {
    setBrief(project.brief || {});
    initial.current = JSON.stringify(project.brief || {});
  }, [project.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key, val) => {
    setBrief((b) => ({ ...b, [key]: val }));
    setSaveState('dirty');
  };

  useDebouncedEffect(() => {
    if (saveState !== 'dirty') return;
    (async () => {
      setSaveState('saving');
      try {
        const patch = {};
        for (const f of BRIEF_FIELDS) patch[f.key] = brief[f.key] ?? '';
        const r = await api.put(`/v1/projects/${project.id}/brief`, patch);
        onSaved(r.data);
        initial.current = JSON.stringify(r.data.brief || {});
        setSaveState('saved');
      } catch (err) {
        setSaveState('dirty');
        toast(err?.response?.data?.error?.message || 'Autosave failed');
      }
    })();
  }, [brief], 700);

  return (
    <div className="grid md:grid-cols-2 gap-5">
      {BRIEF_FIELDS.map((f) => (
        <div key={f.key} className={f.textarea ? 'md:col-span-2' : ''}>
          <Label className="text-xs uppercase tracking-widest text-zinc-400">{f.label}</Label>
          {f.textarea ? (
            <Textarea
              value={brief[f.key] || ''}
              onChange={(e) => set(f.key, e.target.value)}
              placeholder={f.placeholder}
              rows={3}
              maxLength={2000}
              data-testid={`brief-${f.key}-input`}
              className="mt-2 bg-black/20 border-white/10"
            />
          ) : (
            <Input
              value={brief[f.key] || ''}
              onChange={(e) => set(f.key, e.target.value)}
              placeholder={f.placeholder}
              maxLength={500}
              data-testid={`brief-${f.key}-input`}
              className="mt-2 bg-black/20 border-white/10"
            />
          )}
        </div>
      ))}
      <div className="md:col-span-2 flex items-center gap-2 text-xs text-zinc-500 mt-2" data-testid="brief-save-state">
        {saveState === 'saving' && <><Loader2 size={12} className="animate-spin" /> Saving…</>}
        {saveState === 'saved' && <><Check size={12} className="text-emerald-400" /> All changes saved</>}
        {saveState === 'dirty' && <><Save size={12} /> Unsaved changes</>}
      </div>
    </div>
  );
}

function CreativeObjectEditor({ obj, projectId, onChanged, onDeleted }) {
  const [title, setTitle] = useState(obj.title || '');
  const [content, setContent] = useState(obj.content || '');
  const [saveState, setSaveState] = useState('saved');
  const initial = useRef({ title: obj.title || '', content: obj.content || '' });

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
        const r = await api.patch(`/v1/projects/${projectId}/creative-objects/${obj.id}`, {
          title, content,
        });
        initial.current = { title: r.data.title || '', content: r.data.content || '' };
        setSaveState('saved');
        onChanged(r.data);
      } catch (err) {
        setSaveState('dirty');
        toast('Save failed');
      }
    })();
  }, [title, content], 700);

  const del = async () => {
    try {
      await api.delete(`/v1/projects/${projectId}/creative-objects/${obj.id}`);
      onDeleted(obj.id);
      toast('Deleted');
    } catch {
      toast('Delete failed');
    }
  };

  return (
    <div className="card-surface p-5" data-testid={`creative-object-${obj.id}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="chip chip-accent">{obj.type}</span>
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
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button className="p-2 rounded-full text-zinc-500 hover:text-red-400 hover:bg-white/5" data-testid={`creative-object-delete-${obj.id}`}>
              <Trash2 size={14} />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent className="border-white/10" style={{ background: '#12121A' }}>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this item?</AlertDialogTitle>
              <AlertDialogDescription>This can't be undone.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={del} data-testid={`creative-object-confirm-delete-${obj.id}`}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
      <Textarea
        value={content}
        onChange={(e) => { setContent(e.target.value); setSaveState('dirty'); }}
        placeholder="Start writing…"
        rows={6}
        maxLength={100000}
        data-testid={`creative-object-content-${obj.id}`}
        className="bg-black/20 border-white/10 font-mono text-sm"
      />
    </div>
  );
}

function ContentTab({ projectId }) {
  const [items, setItems] = useState(null);
  const [newType, setNewType] = useState('notes');

  const load = useCallback(async () => {
    const r = await api.get(`/v1/projects/${projectId}/creative-objects`);
    setItems(r.data);
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      const r = await api.post(`/v1/projects/${projectId}/creative-objects`, {
        type: newType, title: '', content: '',
      });
      setItems((prev) => [...(prev || []), r.data]);
      toast('New draft added');
    } catch {
      toast('Could not create');
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-sm text-zinc-400">
            Persist any drafts here — notes, outlines, scripts, captions. Autosaved as you type.
          </p>
        </div>
        <Select value={newType} onValueChange={setNewType}>
          <SelectTrigger className="w-40 bg-black/20 border-white/10" data-testid="new-object-type-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CREATIVE_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <button onClick={create} data-testid="new-object-btn" className="btn-primary inline-flex items-center gap-2 !py-2 !px-4 text-sm">
          <Plus size={14} /> Add
        </button>
      </div>
      {items === null ? (
        <div className="text-zinc-500 text-sm flex items-center gap-2">
          <Loader2 size={12} className="animate-spin" /> Loading drafts…
        </div>
      ) : items.length === 0 ? (
        <div className="card-surface p-10 text-center" data-testid="content-empty">
          <FileText className="mx-auto mb-3 text-zinc-500" size={24} />
          <div className="font-display text-lg">No drafts yet.</div>
          <div className="text-sm text-zinc-500 mt-1">Add a note, outline, or script above to begin.</div>
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

function ActivityFeed({ projectId }) {
  const [events, setEvents] = useState(null);
  useEffect(() => {
    api.get(`/v1/projects/${projectId}/activity`).then(r => setEvents(r.data));
  }, [projectId]);
  if (events === null) return <div className="text-zinc-500 text-sm flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Loading…</div>;
  if (events.length === 0) return <div className="text-zinc-500 text-sm">No activity yet.</div>;
  return (
    <ol className="space-y-3" data-testid="project-activity-list">
      {events.map((e) => (
        <li key={e.id} className="text-sm text-zinc-400 flex items-start gap-3">
          <span className="w-1.5 h-1.5 mt-2 rounded-full bg-violet-400/60" />
          <div className="flex-1">
            <span className="text-zinc-200">{e.event_type.replaceAll('_', ' ')}</span>
            <span className="ml-2 text-xs text-zinc-500">{new Date(e.created_at).toLocaleString()}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

const PLACEHOLDER_TABS = {
  research: { icon: Compass, text: 'Research tools will appear here.' },
  direction: { icon: Sparkles, text: 'Direction and angle exploration will appear here.' },
  ship: { icon: Rocket, text: 'Shipping and publishing tools will appear here.' },
};

function PlaceholderPanel({ which }) {
  const { icon: Icon, text } = PLACEHOLDER_TABS[which];
  return (
    <div className="card-surface p-12 text-center" data-testid={`placeholder-${which}`}>
      <div className="w-12 h-12 mx-auto rounded-2xl flex items-center justify-center mb-4"
           style={{ background: 'rgba(138,43,226,0.14)', color: '#C4B5FD' }}>
        <Icon size={20} />
      </div>
      <div className="font-display text-lg">{text}</div>
      <div className="text-sm text-zinc-500 mt-2">Coming in the next milestone.</div>
    </div>
  );
}

export default function ProjectWorkspace() {
  const { id } = useParams();
  const nav = useNavigate();
  const [project, setProject] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState('brief');

  useEffect(() => {
    api.get(`/v1/projects/${id}`)
      .then(r => setProject(r.data))
      .catch(() => setNotFound(true));
  }, [id]);

  const setStatus = async (status) => {
    try {
      const r = await api.patch(`/v1/projects/${id}`, { status });
      setProject(r.data);
      toast(`Status → ${status}`);
    } catch {
      toast('Could not update status');
    }
  };

  const setTitle = async (title) => {
    if (!title.trim() || title === project.title) return;
    try {
      const r = await api.patch(`/v1/projects/${id}`, { title: title.trim() });
      setProject(r.data);
    } catch {
      toast('Could not update title');
    }
  };

  const discard = async () => {
    await api.patch(`/v1/projects/${id}`, { status: 'discarded' });
    toast('Project discarded');
    nav('/app');
  };

  if (notFound) {
    return (
      <div className="max-w-xl mx-auto text-center py-20" data-testid="project-not-found">
        <div className="font-display text-3xl font-semibold mb-2">Project not found.</div>
        <p className="text-zinc-400 mb-6">It may have been discarded, or it belongs to another creator.</p>
        <Link to="/app" className="btn-primary">Back to projects</Link>
      </div>
    );
  }
  if (!project) {
    return <div className="text-zinc-500 flex items-center gap-2"><Loader2 className="animate-spin" size={14} /> Loading project…</div>;
  }

  return (
    <div data-testid="project-workspace">
      <div className="mb-6 flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/app" className="hover:text-white flex items-center gap-1" data-testid="back-to-projects">
          <ArrowLeft size={14} /> Projects
        </Link>
        <ChevronRight size={14} />
        <span className="text-zinc-400">{project.title}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div className="flex-1 min-w-0">
          <div className="chip mb-3 inline-flex items-center gap-1.5">
            <PlatformIcon platform={project.platform} />
            <span className="capitalize">{project.content_type.replace('_', ' ')}</span>
          </div>
          <TitleInput value={project.title} onCommit={setTitle} />
          <div className="text-xs text-zinc-500 mt-2 flex items-center gap-1.5">
            <Clock size={12} /> Updated {new Date(project.updated_at).toLocaleString()}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Select value={project.status} onValueChange={setStatus}>
            <SelectTrigger className="w-40 bg-black/20 border-white/10" data-testid="project-status-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => (
                <SelectItem key={s.value} value={s.value} data-testid={`status-option-${s.value}`}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button className="btn-ghost text-sm inline-flex items-center gap-2" data-testid="project-discard-btn">
                <Trash2 size={14} /> Discard
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent className="border-white/10" style={{ background: '#12121A' }}>
              <AlertDialogHeader>
                <AlertDialogTitle>Discard this project?</AlertDialogTitle>
                <AlertDialogDescription>
                  It'll be hidden from your dashboard. Your brief and drafts stay saved.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={discard} data-testid="project-confirm-discard">Discard</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_280px] gap-8">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-white/[0.03] border border-white/10 p-1 rounded-full">
            <TabsTrigger value="brief" data-testid="tab-brief" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Brief</TabsTrigger>
            <TabsTrigger value="research" data-testid="tab-research" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Research</TabsTrigger>
            <TabsTrigger value="direction" data-testid="tab-direction" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Direction</TabsTrigger>
            <TabsTrigger value="content" data-testid="tab-content" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Content</TabsTrigger>
            <TabsTrigger value="ship" data-testid="tab-ship" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Ship</TabsTrigger>
          </TabsList>
          <TabsContent value="brief" className="mt-6">
            <BriefTab project={project} onSaved={setProject} />
          </TabsContent>
          <TabsContent value="research" className="mt-6"><PlaceholderPanel which="research" /></TabsContent>
          <TabsContent value="direction" className="mt-6"><PlaceholderPanel which="direction" /></TabsContent>
          <TabsContent value="content" className="mt-6"><ContentTab projectId={project.id} /></TabsContent>
          <TabsContent value="ship" className="mt-6"><PlaceholderPanel which="ship" /></TabsContent>
        </Tabs>

        <aside className="card-surface p-5 h-max sticky top-24">
          <div className="text-xs uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
            <ListChecks size={13} /> Activity
          </div>
          <ActivityFeed projectId={project.id} />
        </aside>
      </div>
    </div>
  );
}

function TitleInput({ value, onCommit }) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <input
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={() => onCommit(local)}
      onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
      data-testid="project-title-input"
      className="bg-transparent border-0 outline-none font-display text-3xl md:text-4xl font-semibold tracking-tight w-full p-0 focus:ring-0"
      maxLength={500}
    />
  );
}
