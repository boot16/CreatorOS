import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Plus, Youtube, Instagram, FolderPlus, Clock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';

const CONTENT_TYPES = [
  { value: 'youtube_video', label: 'YouTube Video', platform: 'youtube' },
  { value: 'instagram_reel', label: 'Instagram Reel', platform: 'instagram' },
  { value: 'instagram_post', label: 'Instagram Post', platform: 'instagram' },
  { value: 'instagram_carousel', label: 'Instagram Carousel', platform: 'instagram' },
];

const STATUS_LABEL = {
  idea: 'Idea', researching: 'Researching', developing: 'Developing',
  writing: 'Writing', ready: 'Ready', shipped: 'Shipped', discarded: 'Discarded',
};

const STATUS_COLOR = {
  idea: 'text-zinc-400 border-white/10',
  researching: 'text-cyan-300 border-cyan-400/30',
  developing: 'text-violet-300 border-violet-400/40',
  writing: 'text-amber-300 border-amber-400/30',
  ready: 'text-emerald-300 border-emerald-400/30',
  shipped: 'text-blue-300 border-blue-400/30',
  discarded: 'text-zinc-500 border-white/5',
};

function PlatformIcon({ platform, size = 14 }) {
  if (platform === 'youtube') return <Youtube size={size} className="text-red-400" />;
  return <Instagram size={size} className="text-pink-400" />;
}

function NewProjectDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [contentType, setContentType] = useState('youtube_video');
  const [objective, setObjective] = useState('');
  const [saving, setSaving] = useState(false);
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) { toast('Add a working title first.'); return; }
    setSaving(true);
    try {
      const r = await api.post('/v1/projects', {
        title: title.trim(),
        content_type: contentType,
        objective: objective.trim() || null,
      });
      toast('Project created.');
      setOpen(false);
      setTitle(''); setObjective(''); setContentType('youtube_video');
      if (onCreated) onCreated();
      nav(`/app/projects/${r.data.id}`);
    } catch (err) {
      toast(err?.response?.data?.error?.message || 'Could not create project.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          data-testid="new-project-btn"
          className="btn-primary inline-flex items-center gap-2"
        >
          <Plus size={16} /> New project
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg border-white/10" style={{ background: '#12121A' }}>
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Start a new project</DialogTitle>
          <DialogDescription className="text-sm text-zinc-400">
            A working title and content type are enough — you can flesh out the brief inside.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5 pt-2">
          <div>
            <Label htmlFor="np-title" className="text-xs uppercase tracking-widest text-zinc-400">Working title</Label>
            <Input
              id="np-title"
              data-testid="new-project-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. I Replaced My First Hire With an AI Agent"
              maxLength={500}
              autoFocus
              className="mt-2 bg-black/20 border-white/10"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-zinc-400">Content type</Label>
            <Select value={contentType} onValueChange={setContentType}>
              <SelectTrigger data-testid="new-project-type-select" className="mt-2 bg-black/20 border-white/10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CONTENT_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} data-testid={`new-project-type-${t.value}`}>
                    <span className="inline-flex items-center gap-2">
                      <PlatformIcon platform={t.platform} /> {t.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="np-obj" className="text-xs uppercase tracking-widest text-zinc-400">
              Objective <span className="text-zinc-600 normal-case tracking-normal">(optional)</span>
            </Label>
            <Textarea
              id="np-obj"
              data-testid="new-project-objective-input"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="What do you want this to accomplish?"
              rows={3}
              maxLength={2000}
              className="mt-2 bg-black/20 border-white/10"
            />
          </div>
          <DialogFooter>
            <button
              type="submit"
              data-testid="new-project-submit"
              disabled={saving}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
            >
              {saving ? <Loader2 className="animate-spin" size={14} /> : <Plus size={14} />}
              Create project
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Projects() {
  const [items, setItems] = useState(null);

  const load = async () => {
    try {
      const r = await api.get('/v1/projects');
      setItems(r.data);
    } catch (e) {
      setItems([]);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div data-testid="projects-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-10">
        <div>
          <div className="chip chip-accent mb-3">Your workspace</div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Projects.</h1>
          <p className="mt-3 text-zinc-400 max-w-xl">
            One place for every video, reel, and post. Pick up where you left off — brief, research, and drafts are always saved.
          </p>
        </div>
        <NewProjectDialog onCreated={load} />
      </div>

      {items === null ? (
        <div className="text-zinc-500 flex items-center gap-2">
          <Loader2 className="animate-spin" size={14} /> Loading projects…
        </div>
      ) : items.length === 0 ? (
        <div
          data-testid="projects-empty"
          className="card-surface p-12 text-center max-w-2xl mx-auto"
        >
          <div className="w-14 h-14 mx-auto rounded-2xl flex items-center justify-center mb-4"
               style={{ background: 'rgba(138,43,226,0.14)', color: '#C4B5FD' }}>
            <FolderPlus size={22} />
          </div>
          <div className="font-display text-2xl font-semibold">No projects yet.</div>
          <p className="text-zinc-400 mt-2 max-w-sm mx-auto">
            Every idea becomes a project — with a brief you can return to, research you can save,
            and drafts you never lose.
          </p>
          <div className="mt-6">
            <NewProjectDialog onCreated={load} />
          </div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p, i) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Link
                to={`/app/projects/${p.id}`}
                data-testid={`project-card-${p.id}`}
                className="card-surface p-6 card-hover block h-full"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-zinc-500">
                    <PlatformIcon platform={p.platform} size={12} />
                    {CONTENT_TYPES.find(c => c.value === p.content_type)?.label || p.content_type}
                  </span>
                  <span className={`chip ${STATUS_COLOR[p.status] || ''}`} data-testid={`project-status-${p.id}`}>
                    {STATUS_LABEL[p.status] || p.status}
                  </span>
                </div>
                <h3 className="font-display text-lg font-semibold leading-snug line-clamp-2 mb-6">
                  {p.title}
                </h3>
                <div className="text-xs text-zinc-500 flex items-center gap-1.5">
                  <Clock size={12} /> Updated {new Date(p.updated_at).toLocaleString()}
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
