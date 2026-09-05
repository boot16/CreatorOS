import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Sparkles, Radar, Lightbulb, Users, TrendingUp } from 'lucide-react';
import RadialScore from '../components/RadialScore';
import Sparkline from '../components/Sparkline';
import { API } from '../lib/api';
import { useBootstrap } from '../lib/bootstrap';

const benefits = [
  { icon: Sparkles, title: 'Your channel, decoded', text: 'CreatorOS reads your content DNA — pillars, formats, style — and shows you what really moves your audience.' },
  { icon: TrendingUp, title: 'Trends before they saturate', text: 'Radar surfaces what your niche is about to care about, not what already peaked.' },
  { icon: Lightbulb, title: 'The next video, not just an idea', text: 'Concept, titles, hooks, and structure — grounded in your voice and the data behind the score.' },
  { icon: Users, title: 'Collaborators that actually fit', text: 'Compatibility scored across audience, topics, complementarity — not just vibes.' },
];

export default function Landing() {
  const boot = useBootstrap();
  const nav = useNavigate();

  // Signed-in users skip the landing page.
  useEffect(() => {
    if (!boot.loading && boot.is_authenticated) {
      nav(boot.onboarding_complete ? '/app' : '/onboarding', { replace: true });
    }
  }, [boot.loading, boot.is_authenticated, boot.onboarding_complete, nav]);

  const startGoogle = () => { window.location.href = `${API}/auth/google/login`; };

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[900px] rounded-full"
           style={{ background: 'radial-gradient(circle, rgba(138,43,226,0.22), transparent 60%)' }} />

      <header className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between relative z-10">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
          <span className="font-display text-lg font-semibold">CreatorOS</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={startGoogle} data-testid="header-signin-btn" className="btn-ghost text-sm">Sign in</button>
          <Link to="/onboarding" data-testid="header-demo-link" className="btn-ghost text-sm">View Demo</Link>
        </div>
      </header>

      <section className="max-w-7xl mx-auto px-6 pt-16 pb-24 relative z-10 grid lg:grid-cols-[1.05fr_1fr] gap-16 items-center">
        <div>
          <div className="chip chip-accent mb-6" data-testid="hero-eyebrow">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400" /> Contest build · v1
          </div>
          <h1 className="font-display text-5xl md:text-6xl font-bold leading-[1.02] tracking-tight">
            Know what to <span className="gradient-text">create next</span>,
            <br />and who to create it with.
          </h1>
          <p className="mt-6 text-lg text-zinc-400 max-w-xl leading-relaxed">
            Your channel's data, current trends, and a network of creators — turned into one clear next move.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <button onClick={startGoogle} data-testid="hero-signin-btn" className="btn-primary inline-flex items-center gap-2">
              Continue with Google <ArrowRight size={16} />
            </button>
            <Link to="/onboarding" data-testid="hero-primary-cta" className="btn-ghost inline-flex items-center gap-2">
              View Demo
            </Link>
            <a href="#how" className="btn-ghost">See how it works</a>
          </div>
          <div className="mt-10 flex items-center gap-6 text-xs text-zinc-500">
            <div>No followers needed · Real workspace, real drafts, real DNA</div>
          </div>
        </div>

        {/* Hero visual: floating opportunity card */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="relative"
          data-testid="hero-visual"
        >
          <div className="absolute -inset-6 rounded-3xl blur-3xl opacity-40"
               style={{ background: 'radial-gradient(circle, rgba(138,43,226,0.5), transparent 70%)' }} />
          <div className="relative card-surface p-6 md:p-8">
            <div className="flex items-center justify-between mb-6">
              <span className="chip chip-accent">Top opportunity</span>
              <span className="text-xs text-zinc-500">for @alexmorganai</span>
            </div>
            <div className="flex items-start gap-6">
              <RadialScore value={91} size={112} sublabel="score" testId="hero-score" />
              <div className="flex-1 min-w-0">
                <div className="text-[11px] uppercase tracking-widest text-violet-300 mb-2">AI Employees · Emerging</div>
                <h3 className="font-display text-xl font-semibold leading-snug">
                  I Replaced My First Employee With an AI Agent — 30 Day Log
                </h3>
                <div className="mt-4 flex items-center gap-4 text-xs text-zinc-400">
                  <div className="flex items-center gap-1"><TrendingUp size={14} className="text-emerald-400" /> +267% momentum</div>
                  <Sparkline data={[4,7,11,19,32,48,61]} width={80} height={24} />
                </div>
              </div>
            </div>
            <div className="divider my-6" />
            <div className="grid grid-cols-3 gap-3">
              {[
                { k: 'Trend Fit', v: 96 },
                { k: 'Creator Fit', v: 94 },
                { k: 'Format Fit', v: 92 },
              ].map(x => (
                <div key={x.k} className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500">{x.k}</div>
                  <div className="font-display text-2xl font-semibold text-white mt-1">{x.v}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      <section id="how" className="max-w-7xl mx-auto px-6 pb-24 relative z-10">
        <div className="mb-10">
          <div className="text-xs uppercase tracking-widest text-violet-300 mb-3">What it does</div>
          <h2 className="font-display text-3xl md:text-4xl font-semibold tracking-tight max-w-2xl">
            The reasoning is shown — not just the answer.
          </h2>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          {benefits.map(({ icon: Icon, title, text }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="card-surface p-6 card-hover"
              data-testid={`benefit-${i}`}
            >
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                   style={{ background: 'rgba(138,43,226,0.14)', color: '#C4B5FD' }}>
                <Icon size={18} />
              </div>
              <h3 className="font-display text-lg font-semibold mb-2">{title}</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">{text}</p>
            </motion.div>
          ))}
        </div>

        <div className="mt-16 text-center">
          <Link to="/onboarding" data-testid="footer-cta" className="btn-primary inline-flex items-center gap-2">
            Try the live demo <ArrowRight size={16} />
          </Link>
        </div>
      </section>
    </div>
  );
}
