import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowRight, Loader2, Sparkles, Youtube, Instagram, PencilLine, BookOpen, Music, Camera, Palette, Mic, Users, Rocket, Radio } from 'lucide-react';
import { api } from '../lib/api';
import { useBootstrap } from '../lib/bootstrap';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const CREATOR_TYPES = [
  { id: 'youtuber', label: 'YouTuber', icon: Youtube },
  { id: 'instagram_creator', label: 'Instagram creator', icon: Instagram },
  { id: 'writer', label: 'Writer', icon: PencilLine },
  { id: 'educator', label: 'Educator', icon: BookOpen },
  { id: 'musician', label: 'Musician', icon: Music },
  { id: 'artist', label: 'Artist', icon: Palette },
  { id: 'photographer', label: 'Photographer', icon: Camera },
  { id: 'podcaster', label: 'Podcaster', icon: Mic },
  { id: 'founder', label: 'Founder', icon: Rocket },
  { id: 'streamer', label: 'Streamer', icon: Radio },
  { id: 'community_builder', label: 'Community builder', icon: Users },
];

const PLATFORMS = ['youtube', 'instagram', 'tiktok', 'twitter', 'substack', 'linkedin', 'other'];
const FORMATS = ['experiment', 'tutorial', 'story', 'listicle', 'interview', 'review', 'reaction', 'vlog'];
const GOALS = [
  { id: 'grow', label: 'Grow audience' },
  { id: 'monetize', label: 'Monetize' },
  { id: 'educate', label: 'Educate' },
  { id: 'community', label: 'Build community' },
  { id: 'ship_more', label: 'Ship more consistently' },
];

export default function Onboarding() {
  const nav = useNavigate();
  const boot = useBootstrap();
  const [types, setTypes] = useState(new Set());
  const [text, setText] = useState('');
  const [audience, setAudience] = useState('');
  const [platforms, setPlatforms] = useState(new Set());
  const [formats, setFormats] = useState(new Set());
  const [goals, setGoals] = useState(new Set(['grow']));
  const [sourceUrl, setSourceUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // If already onboarded (real user with DNA, or demo), skip.
  useEffect(() => {
    if (!boot.loading && boot.onboarding_complete) {
      nav('/app', { replace: true });
    }
  }, [boot.loading, boot.onboarding_complete, nav]);

  // Not signed in — bounce to landing
  useEffect(() => {
    if (!boot.loading && !boot.is_authenticated && !boot.is_demo) {
      nav('/', { replace: true });
    }
  }, [boot.loading, boot.is_authenticated, boot.is_demo, nav]);

  const toggle = (setter, value) => {
    setter((prev) => {
      const s = new Set(prev);
      s.has(value) ? s.delete(value) : s.add(value);
      return s;
    });
  };

  const submit = async () => {
    if (types.size === 0) { toast('Pick at least one creator type.'); return; }
    if (text.trim().length < 30) { toast('Tell us a bit more about what you create (30+ characters).'); return; }
    setSubmitting(true);
    try {
      await api.post('/v1/onboarding', {
        creator_types: [...types],
        onboarding_text: text.trim(),
        topics: [],
        intended_audience: audience.trim() || null,
        platforms: [...platforms],
        preferred_formats: [...formats],
        goals: [...goals],
        connected_sources: sourceUrl.trim() ? [sourceUrl.trim()] : [],
      });
      await boot.reload();
      toast('Your Creator DNA is ready.');
      nav('/app', { replace: true });
    } catch (err) {
      toast(err?.response?.data?.error?.message || 'Onboarding failed. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (boot.loading) {
    return <div className="min-h-screen flex items-center justify-center text-zinc-500"><Loader2 className="animate-spin" size={16} /></div>;
  }

  return (
    <div className="min-h-screen">
      <header className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="onboarding-home">
          <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
          <span className="font-display text-lg font-semibold">CreatorOS</span>
        </Link>
        <span className="text-xs text-zinc-500">First-run setup</span>
      </header>

      <div className="max-w-4xl mx-auto px-6 pb-24" data-testid="onboarding-page">
        <div className="chip chip-accent mb-6">Onboarding</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
          Tell CreatorOS about you.
        </h1>
        <p className="mt-4 text-zinc-400 max-w-2xl">
          No followers needed. Just describe what you make (or want to make). We'll build your Creator DNA
          and use it across every AI feature.
        </p>

        {/* Creator types */}
        <section className="mt-12">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">What kind of creator are you?</Label>
          <p className="text-xs text-zinc-500 mt-1 mb-4">Pick everything that fits — even if you're just starting.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {CREATOR_TYPES.map((t) => {
              const active = types.has(t.id);
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => toggle(setTypes, t.id)}
                  data-testid={`ct-${t.id}`}
                  className="text-left p-4 rounded-2xl border transition-colors"
                  style={active
                    ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.08)' }
                    : { borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}
                >
                  <div className="flex items-center gap-3">
                    <Icon size={16} className={active ? 'text-violet-300' : 'text-zinc-400'} />
                    <span className="text-sm font-medium">{t.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* Free text */}
        <section className="mt-12">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">Tell us about yourself</Label>
          <p className="text-xs text-zinc-500 mt-1 mb-3">
            Who you are, what you make, and who it's for. This is the most important input.
          </p>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="I'm a software engineering student interested in AI and startups. I want to make educational YouTube videos explaining complicated AI concepts simply, for other students and early-stage developers. I prefer practical experiments over news commentary."
            rows={7}
            maxLength={6000}
            className="bg-black/20 border-white/10 font-mono text-sm leading-relaxed"
            data-testid="onboarding-text-input"
          />
          <div className="text-xs text-zinc-500 mt-1">{text.length}/6000</div>
        </section>

        {/* Structured extras */}
        <section className="mt-10 grid md:grid-cols-2 gap-6">
          <div>
            <Label className="text-xs uppercase tracking-widest text-zinc-400">Intended audience (optional)</Label>
            <Input
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              placeholder="e.g. college students learning AI"
              maxLength={500}
              className="mt-2 bg-black/20 border-white/10"
              data-testid="onboarding-audience-input"
            />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-widest text-zinc-400">Existing profile/channel URL (optional)</Label>
            <Input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://youtube.com/@… or Instagram/etc."
              maxLength={500}
              className="mt-2 bg-black/20 border-white/10"
              data-testid="onboarding-source-input"
            />
            <div className="text-xs text-zinc-500 mt-1">We won't crawl it — this is just noted in your DNA.</div>
          </div>
        </section>

        <section className="mt-10">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">Platforms (optional)</Label>
          <div className="flex flex-wrap gap-2 mt-3">
            {PLATFORMS.map((p) => (
              <button
                key={p}
                onClick={() => toggle(setPlatforms, p)}
                data-testid={`plat-${p}`}
                className="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                style={platforms.has(p)
                  ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.14)', color: '#E9D5FF' }
                  : { borderColor: 'rgba(255,255,255,0.08)', color: '#A1A1AA' }}
              >
                {p}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-8">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">Preferred formats (optional)</Label>
          <div className="flex flex-wrap gap-2 mt-3">
            {FORMATS.map((f) => (
              <button
                key={f}
                onClick={() => toggle(setFormats, f)}
                data-testid={`fmt-${f}`}
                className="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                style={formats.has(f)
                  ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.14)', color: '#E9D5FF' }
                  : { borderColor: 'rgba(255,255,255,0.08)', color: '#A1A1AA' }}
              >
                {f}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-8">
          <Label className="text-xs uppercase tracking-widest text-zinc-400">Goals (optional)</Label>
          <div className="flex flex-wrap gap-2 mt-3">
            {GOALS.map((g) => (
              <button
                key={g.id}
                onClick={() => toggle(setGoals, g.id)}
                data-testid={`goal-${g.id}`}
                className="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                style={goals.has(g.id)
                  ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.14)', color: '#E9D5FF' }
                  : { borderColor: 'rgba(255,255,255,0.08)', color: '#A1A1AA' }}
              >
                {g.label}
              </button>
            ))}
          </div>
        </section>

        <div className="mt-12 flex items-center gap-3">
          <button
            onClick={submit}
            disabled={submitting}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
            data-testid="onboarding-submit"
          >
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {submitting ? 'Building your DNA…' : 'Build my Creator DNA'}
            {!submitting && <ArrowRight size={16} />}
          </button>
          <span className="text-xs text-zinc-500">Takes a few seconds. You can edit anything later.</span>
        </div>
      </div>
    </div>
  );
}
