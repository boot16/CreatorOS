import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { API, DEMO_CREATOR_ID } from '../lib/api';
import { Send, Sparkles, Loader2 } from 'lucide-react';
import { getClientId } from '../lib/client';

const SUGGESTIONS = [
  "Give me a 3-video plan for next week that fits my DNA",
  "Rewrite this title so it lands harder: 'AI Employees Explained'",
  "What's a strong cold-open for a 'Vibe Coding' video?",
  "Which of my formats should I lean into this month, and why?",
];

export default function Studio() {
  const [sessionId] = useState(() => localStorage.getItem('studio-session') || (() => {
    const s = crypto.randomUUID?.() || String(Date.now());
    localStorage.setItem('studio-session', s);
    return s;
  })());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/assistant/history/${sessionId}`).then(r => r.json()).then(setMessages).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, streaming]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || streaming) return;
    setInput('');
    const next = [...messages, { role: 'user', content }, { role: 'assistant', content: '' }];
    setMessages(next);
    setStreaming(true);

    try {
      const resp = await fetch(`${API}/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId() },
        body: JSON.stringify({
          session_id: sessionId,
          creator_id: DEMO_CREATOR_ID,
          messages: [...messages, { role: 'user', content }].map(m => ({ role: m.role, content: m.content })),
        }),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let acc = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: 'assistant', content: acc };
          return copy;
        });
      }
    } catch (e) {
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', content: '(stream failed — try again)' };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="studio-page">
      <div className="mb-6">
        <div className="chip chip-accent mb-3"><Sparkles size={12} /> Studio</div>
        <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">Your AI creative partner.</h1>
        <p className="mt-3 text-zinc-400 max-w-xl">Grounded in your DNA. Plan videos, riff on titles, work through the week.</p>
      </div>

      <div className="grid lg:grid-cols-[1fr_300px] gap-6">
        <div className="card-surface flex flex-col" style={{ height: '640px' }}>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="studio-messages">
            {messages.length === 0 && (
              <div className="text-center text-zinc-500 pt-16">
                <Sparkles className="mx-auto mb-3 text-violet-400" size={22} />
                <div>Start a conversation. The assistant knows Alex's pillars, formats, and voice.</div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-violet-500/20 text-white border border-violet-500/30'
                      : 'bg-white/[0.03] text-zinc-100 border border-white/10'
                  }`}
                  data-testid={`msg-${m.role}-${i}`}
                >
                  {m.content || (streaming && i === messages.length - 1 ? <Loader2 className="animate-spin" size={14} /> : '')}
                </div>
              </div>
            ))}
          </div>
          <div className="p-4 border-t border-white/5">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && send()}
                disabled={streaming}
                placeholder="Ask, brainstorm, or plan…"
                data-testid="studio-input"
                className="flex-1 bg-white/[0.03] border border-white/10 rounded-full px-5 py-3 text-sm focus:outline-none focus:border-violet-500 disabled:opacity-50"
              />
              <button
                onClick={() => send()}
                disabled={streaming || !input.trim()}
                data-testid="studio-send-btn"
                className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
              >
                {streaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500">Try one</div>
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              onClick={() => send(s)}
              disabled={streaming}
              data-testid={`studio-suggest-${i}`}
              className="text-left w-full p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:border-violet-500/50 transition-colors text-sm text-zinc-200 disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
