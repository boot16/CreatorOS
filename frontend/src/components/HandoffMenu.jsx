import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { api, API } from '../lib/api';
import { toast } from 'sonner';
import { Copy, Mail, MessageSquare, ExternalLink, Loader2, Info } from 'lucide-react';

export default function HandoffMenu({ oppId, open, onOpenChange }) {
  const [brief, setBrief] = useState(null);
  const [status, setStatus] = useState(null);
  const [sending, setSending] = useState(false);
  const [slackSetup, setSlackSetup] = useState(false);

  useEffect(() => {
    if (open && !brief) {
      api.get(`/handoff/brief/${oppId}`).then(r => setBrief(r.data));
      api.get('/handoff/status').then(r => setStatus(r.data));
    }
  }, [open, oppId, brief]);

  const copy = () => {
    if (!brief) return;
    navigator.clipboard.writeText(brief.markdown);
    toast.success('Brief copied — paste anywhere');
  };

  const email = () => {
    if (!brief) return;
    const url = `mailto:?subject=${encodeURIComponent(brief.subject)}&body=${encodeURIComponent(brief.markdown)}`;
    window.location.href = url;
  };

  const sendSlack = async () => {
    if (!status?.slack?.configured) {
      setSlackSetup(true);
      return;
    }
    setSending(true);
    try {
      await api.post('/handoff/slack', { opportunity_id: oppId });
      toast.success('Sent to Slack');
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Slack send failed');
    }
    setSending(false);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-lg border-white/10" style={{ background: '#12121A' }} data-testid="handoff-modal">
          <DialogHeader><DialogTitle className="font-display text-xl">Send to editor</DialogTitle></DialogHeader>
          <p className="text-sm text-zinc-400">Full brief with reasoning, scores, and link back to the opportunity.</p>

          <div className="mt-4 space-y-2">
            <button data-testid="handoff-copy" onClick={copy} className="w-full flex items-center gap-3 p-3 rounded-xl border border-white/10 hover:border-violet-500/50 text-left transition-colors">
              <Copy size={16} className="text-violet-300" />
              <div>
                <div className="text-sm text-zinc-100 font-medium">Copy brief</div>
                <div className="text-xs text-zinc-500">Markdown — paste into Notion, Linear, Google Docs</div>
              </div>
            </button>

            <button data-testid="handoff-email" onClick={email} className="w-full flex items-center gap-3 p-3 rounded-xl border border-white/10 hover:border-violet-500/50 text-left transition-colors">
              <Mail size={16} className="text-violet-300" />
              <div>
                <div className="text-sm text-zinc-100 font-medium">Email brief</div>
                <div className="text-xs text-zinc-500">Opens your email client with subject + body pre-filled</div>
              </div>
            </button>

            <button data-testid="handoff-slack" onClick={sendSlack} disabled={sending} className="w-full flex items-center gap-3 p-3 rounded-xl border border-white/10 hover:border-violet-500/50 text-left transition-colors disabled:opacity-50">
              {sending ? <Loader2 size={16} className="animate-spin text-violet-300" /> : <MessageSquare size={16} className="text-violet-300" />}
              <div className="flex-1">
                <div className="text-sm text-zinc-100 font-medium flex items-center gap-2">
                  Post to Slack
                  {!status?.slack?.configured && <span className="chip text-[9px] px-2">setup</span>}
                </div>
                <div className="text-xs text-zinc-500">{status?.slack?.configured ? 'Sends to your configured Slack channel' : 'Add a webhook URL to enable'}</div>
              </div>
            </button>
          </div>

          {brief && (
            <details className="mt-4">
              <summary className="text-xs text-zinc-500 cursor-pointer hover:text-white">Preview brief</summary>
              <pre className="mt-2 p-3 rounded-lg bg-black/40 border border-white/5 text-[11px] text-zinc-300 whitespace-pre-wrap max-h-64 overflow-auto">{brief.markdown}</pre>
            </details>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={slackSetup} onOpenChange={setSlackSetup}>
        <DialogContent className="max-w-lg border-white/10" style={{ background: '#12121A' }} data-testid="slack-setup-modal">
          <DialogHeader><DialogTitle className="font-display text-xl flex items-center gap-2"><Info size={18}/> Slack setup</DialogTitle></DialogHeader>
          <p className="text-sm text-zinc-400">Add a Slack Incoming Webhook to enable direct posting. One-time, ~3 minutes.</p>
          <ol className="mt-4 space-y-3">
            {(status?.slack?.setup_guide?.steps || []).map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-zinc-200">
                <span className="w-6 h-6 shrink-0 rounded-full bg-violet-500/15 text-violet-300 flex items-center justify-center text-xs font-mono">{i+1}</span>
                <span className="leading-snug">{s}</span>
              </li>
            ))}
          </ol>
          <a href="https://api.slack.com/apps" target="_blank" rel="noreferrer" className="btn-primary inline-flex items-center gap-2 mt-4 self-start">
            Open Slack API <ExternalLink size={14} />
          </a>
        </DialogContent>
      </Dialog>
    </>
  );
}
