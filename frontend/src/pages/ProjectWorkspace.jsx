import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Save, Check, Loader2, Youtube, Instagram, Trash2, Plus,
  FileText, ListChecks, Sparkles, Rocket, ChevronRight, Clock, MessageSquare,
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
import { ResearchTab, ContentTab, ProjectAssistant } from './ProjectAI';
import ProjectIdea from './ProjectIdea';
import ProjectDirection from './ProjectDirection';

const STATUSES = [
  { value: 'idea', label: 'Idea' },
  { value: 'researching', label: 'Researching' },
  { value: 'developing', label: 'Developing' },
  { value: 'writing', label: 'Writing' },
  { value: 'ready', label: 'Ready' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'discarded', label: 'Discarded' },
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

function ShipPlaceholder() {
  return (
    <div className="card-surface p-12 text-center" data-testid="placeholder-ship">
      <div className="w-12 h-12 mx-auto rounded-2xl flex items-center justify-center mb-4"
           style={{ background: 'rgba(138,43,226,0.14)', color: '#C4B5FD' }}>
        <Rocket size={20} />
      </div>
      <div className="font-display text-lg">Shipping and publishing tools will appear here.</div>
      <div className="text-sm text-zinc-500 mt-2">Coming in the next milestone.</div>
    </div>
  );
}

export default function ProjectWorkspace() {
  const { id } = useParams();
  const nav = useNavigate();
  const [project, setProject] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState('idea');
  const [sideTab, setSideTab] = useState('activity');
  const [activityBump, setActivityBump] = useState(0);

  const reloadProject = useCallback(async () => {
    try {
      const r = await api.get(`/v1/projects/${id}`);
      setProject(r.data);
      setActivityBump((x) => x + 1);
    } catch {
      setNotFound(true);
    }
  }, [id]);

  useEffect(() => { reloadProject(); }, [reloadProject]);

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
          <TabsList className="bg-white/[0.03] border border-white/10 p-1 rounded-full flex flex-wrap h-auto gap-1">
            <TabsTrigger value="idea" data-testid="tab-idea" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Idea</TabsTrigger>
            <TabsTrigger value="brief" data-testid="tab-brief" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Brief</TabsTrigger>
            <TabsTrigger value="research" data-testid="tab-research" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Research</TabsTrigger>
            <TabsTrigger value="direction" data-testid="tab-direction" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Direction</TabsTrigger>
            <TabsTrigger value="content" data-testid="tab-content" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Content</TabsTrigger>
            <TabsTrigger value="ship" data-testid="tab-ship" className="rounded-full data-[state=active]:bg-violet-500/20 data-[state=active]:text-violet-100">Ship</TabsTrigger>
          </TabsList>
          <TabsContent value="idea" className="mt-6">
            <ProjectIdea
              project={project}
              onActivityChanged={() => setActivityBump((x) => x + 1)}
            />
          </TabsContent>
          <TabsContent value="brief" className="mt-6">
            <BriefTab project={project} onSaved={setProject} />
          </TabsContent>
          <TabsContent value="research" className="mt-6">
            <ResearchTab
              project={project}
              onProjectChanged={reloadProject}
              onCreativeObjectsChanged={() => setActivityBump((x) => x + 1)}
            />
          </TabsContent>
          <TabsContent value="direction" className="mt-6">
            <ProjectDirection
              project={project}
              onProjectChanged={reloadProject}
              onActivityChanged={() => setActivityBump((x) => x + 1)}
            />
          </TabsContent>
          <TabsContent value="content" className="mt-6">
            <ContentTab project={project} onProjectChanged={reloadProject} />
          </TabsContent>
          <TabsContent value="ship" className="mt-6"><ShipPlaceholder /></TabsContent>
        </Tabs>

        <aside className="h-max sticky top-24 space-y-3" data-testid="workspace-sidebar">
          <div className="inline-flex rounded-full border border-white/10 p-1 bg-white/[0.02] w-full">
            <button
              onClick={() => setSideTab('activity')}
              data-testid="side-tab-activity"
              className={`flex-1 px-3 py-1.5 rounded-full text-xs font-medium flex items-center justify-center gap-1.5 ${sideTab === 'activity' ? 'bg-violet-500/20 text-white' : 'text-zinc-400'}`}
            >
              <ListChecks size={12} /> Activity
            </button>
            <button
              onClick={() => setSideTab('assistant')}
              data-testid="side-tab-assistant"
              className={`flex-1 px-3 py-1.5 rounded-full text-xs font-medium flex items-center justify-center gap-1.5 ${sideTab === 'assistant' ? 'bg-violet-500/20 text-white' : 'text-zinc-400'}`}
            >
              <MessageSquare size={12} /> Assistant
            </button>
          </div>
          {sideTab === 'activity' ? (
            <div className="card-surface p-5">
              <ActivityFeed key={activityBump} projectId={project.id} />
            </div>
          ) : (
            <ProjectAssistant projectId={project.id} />
          )}
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
