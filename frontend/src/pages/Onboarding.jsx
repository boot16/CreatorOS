import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowRight, Youtube, Loader2, Info, LogIn } from 'lucide-react';
import { api, API } from '../lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';

const GOALS = [
  { id: 'grow', label: 'Grow subscribers', desc: 'Reach new audience' },
  { id: 'monetize', label: 'Monetize consistently', desc: 'Sponsorships & products' },
  { id: 'collab', label: 'Find collaborators', desc: 'Grow through partnerships' },
  { id: 'trends', label: 'Ride trends earlier', desc: 'Get to topics first' },
  { id: 'workflow', label: 'Ship more consistently', desc: 'Ideas → published, faster' },
];

export default function Onboarding() {
  const nav = useNavigate();
  const [picked, setPicked] = useState(new Set(['grow', 'trends']));
  const [connecting, setConnecting] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [user, setUser] = useState(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const [setup, setSetup] = useState(null);

  useEffect(() => {
    let alive = true;
    api.get('/auth/status')
      .then(({ data }) => { if (alive) user !== data.user && setUser(data.user || null); })
      .catch(() => { if (alive) setUser(null); })
      .finally(() => { if (alive) setCheckingAuth(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (id) => {
    const s = new Set(picked);
    s.has(id) ? s.delete(id) : s.add(id);
    setPicked(s);
  };

  const persistThenGo = async () => {
    if (!user) {
      window.location.href = `${API}/auth/google/login`;
      return;
    }
    try {
      await api.put('/v1/creator-intent', {
        primary_goal: [...picked][0] || null,
        secondary_goals: [...picked].slice(1),
      });
      nav('/dna-reveal');
    } catch (err) {
      if (err?.response?.status === 401) {
        toast.error('Your session expired. Please sign in again.');
      } else {
        toast.error('Could not save your onboarding choices.');
      }
    }
  };

  const connectYouTube = async () => {
    if (!user) {
      window.location.href = `${API}/auth/google/login`;
      return;
    }
    setConnecting(true);
    try {
      const { data } = await api.get('/auth/status');
      if (!data.configured) {
        setSetup(data.setup_guide);
        setSetupOpen(true);
      } else {
        window.location.href = `${API}/auth/youtube/connect`;
      }
    } catch {
      toast.error('Could not check Google/YouTube configuration.');
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="onboarding-home">
          <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
          <span className="font-display text-lg font-semibold">CreatorOS</span>
        </Link>
        <span className="text-xs text-zinc-500">
          {checkingAuth ? 'Checking account…' : user ? `Signed in as ${user.name || user.email || 'creator'}` : 'Account required'}
        </span>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="chip chip-accent mb-6">Onboarding</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
          What are you optimizing for?
        </h1>
        <p className="mt-4 text-zinc-400">
          Your CreatorOS account works without a social connection. Connect YouTube only if you want CreatorOS to learn from your channel.
        </p>

        <div className="mt-10 grid sm:grid-cols-2 gap-3">
          {GOALS.map(g => {
            const active = picked.has(g.id);
            return (
              <button
                key={g.id}
                onClick={() => toggle(g.id)}
                data-testid={`goal-${g.id}`}
                className="text-left card-surface p-5 card-hover"
                style={active ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.06)'} : {}}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-display font-semibold text-white">{g.label}</div>
                    <div className="text-sm text-zinc-500 mt-1">{g.desc}</div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border ${active ? 'bg-violet-500 border-violet-400' : 'border-white/20'}`}>
                    {active && <div className="w-full h-full flex items-center justify-center text-white text-[11px]">✓</div>}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-12 flex flex-wrap items-center gap-3">
          {!checkingAuth && !user ? (
            <button onClick={() => { window.location.href = `${API}/auth/google/login`; }} className="btn-primary inline-flex items-center gap-2" data-testid="google-login-btn">
              <LogIn size={16} /> Sign in with Google
            </button>
          ) : (
            <button data-testid="continue-btn" onClick={persistThenGo} disabled={checkingAuth} className="btn-primary inline-flex items-center gap-2 disabled:opacity-60">
              Continue <ArrowRight size={16} />
            </button>
          )}

          <button
            data-testid="connect-youtube-btn"
            onClick={connectYouTube}
            disabled={connecting || checkingAuth || !user}
            className="btn-ghost inline-flex items-center gap-2 disabled:opacity-50"
          >
            {connecting ? <Loader2 size={16} className="animate-spin" /> : <Youtube size={16} />}
            {user?.youtube_connected ? 'Reconnect YouTube' : 'Connect YouTube'}
          </button>
          <span className="text-xs text-zinc-500 ml-2">Optional · YouTube read-only access</span>
        </div>
      </div>

      <Dialog open={setupOpen} onOpenChange={setSetupOpen}>
        <DialogContent className="max-w-lg border-white/10" style={{ background: '#12121A' }} data-testid="setup-modal">
          <DialogHeader>
            <DialogTitle className="font-display text-xl flex items-center gap-2"><Info size={18} /> YouTube setup required</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">Google OAuth must be configured before a real YouTube account can be connected.</p>
          <ol className="mt-4 space-y-3">
            {(setup?.steps || []).map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-zinc-200">
                <span className="w-6 h-6 shrink-0 rounded-full bg-violet-500/15 text-violet-300 flex items-center justify-center text-xs font-mono">{i+1}</span>
                <span className="leading-snug">{s}</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 p-3 rounded-lg bg-white/5 border border-white/10 text-xs">
            <div className="text-zinc-500 uppercase tracking-widest text-[10px] mb-1">Redirect URI</div>
            <code className="text-violet-300 break-all">{setup?.redirect_uri}</code>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
