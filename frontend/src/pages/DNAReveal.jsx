import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Loader2 } from 'lucide-react';

const STEPS = [
  { key: 'channel', label: 'Parsing channel history' },
  { key: 'pillars', label: 'Identifying content pillars' },
  { key: 'formats', label: 'Scoring format performance' },
  { key: 'style', label: 'Fingerprinting voice & pacing' },
  { key: 'audience', label: 'Mapping audience interests' },
  { key: 'trends', label: 'Cross-referencing live trends' },
];

export default function DNAReveal() {
  const nav = useNavigate();
  const [done, setDone] = useState(0);

  useEffect(() => {
    if (done >= STEPS.length) {
      const t = setTimeout(() => nav('/app/dna'), 700);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setDone(d => d + 1), 550);
    return () => clearTimeout(t);
  }, [done, nav]);

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center">
      <div className="pointer-events-none absolute inset-0"
           style={{ background: 'radial-gradient(circle at 50% 40%, rgba(138,43,226,0.22), transparent 55%)' }} />
      <div className="pointer-events-none absolute inset-0 opacity-40"
           style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
                    backgroundSize: '40px 40px' }} />

      <div className="relative z-10 w-full max-w-xl px-6">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="chip chip-accent mb-6">Creator DNA · Analyzing</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight leading-tight">
            Reading Alex Morgan's channel.
          </h1>
          <p className="mt-3 text-zinc-400">124K subs · 20 videos · niche: AI + Entrepreneurship</p>
        </motion.div>

        <div className="mt-10 space-y-3" data-testid="dna-steps">
          {STEPS.map((s, i) => (
            <AnimatePresence key={s.key}>
              {i <= done && (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35 }}
                  className="flex items-center gap-3 card-surface px-4 py-3"
                  data-testid={`dna-step-${s.key}`}
                >
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center ${
                    i < done ? 'bg-emerald-500/15 text-emerald-400' : 'bg-violet-500/15 text-violet-300'
                  }`}>
                    {i < done ? <Check size={14} /> : <Loader2 size={14} className="animate-spin" />}
                  </div>
                  <span className="text-sm text-zinc-200">{s.label}</span>
                  <span className={`ml-auto text-xs ${i < done ? 'text-emerald-400' : 'text-zinc-500'}`}>
                    {i < done ? 'done' : 'running…'}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          ))}
        </div>

        {done >= STEPS.length && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 text-sm text-zinc-500 text-center">
            Compiling DNA report…
          </motion.div>
        )}
      </div>
    </div>
  );
}
