import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { api, DEMO_CREATOR_ID } from '../lib/api';
import { Calendar as CalIcon, Plus, X, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function startOfWeek(d = new Date()) {
  const dt = new Date(d);
  const day = (dt.getDay() + 6) % 7; // Monday=0
  dt.setDate(dt.getDate() - day);
  dt.setHours(0, 0, 0, 0);
  return dt;
}

function ymd(d) {
  return d.toISOString().slice(0, 10);
}

const stageColor = (s) => ({
  Emerging: '#10B981', Accelerating: '#8A2BE2', Mainstream: '#F59E0B', Saturated: '#EF4444',
}[s] || '#8A2BE2');

export default function WeeklyPlan() {
  const [weekStart, setWeekStart] = useState(startOfWeek());
  const [plan, setPlan] = useState([]);
  const [opps, setOpps] = useState([]);
  const [dragging, setDragging] = useState(null);
  const [dragOver, setDragOver] = useState(null);

  const load = async () => {
    const [p, o] = await Promise.all([
      api.get('/calendar'),
      api.get(`/creators/${DEMO_CREATOR_ID}/opportunities`),
    ]);
    setPlan(p.data);
    setOpps(o.data.sort((a, b) => b.score - a.score));
  };
  useEffect(() => { load(); }, []);

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart); d.setDate(d.getDate() + i); return d;
  });

  const planForDay = (d) => plan.filter(p => p.date === ymd(d));

  const onDropOnDay = async (dayIdx) => {
    const date = ymd(days[dayIdx]);
    if (!dragging) return;
    if (dragging.type === 'new') {
      await api.post('/calendar', { opportunity_id: dragging.oppId, date });
      toast('Added to plan');
    } else if (dragging.type === 'move') {
      await api.patch(`/calendar/${dragging.planId}`, { date });
    }
    setDragging(null); setDragOver(null);
    load();
  };

  const removePlan = async (id) => {
    await api.delete(`/calendar/${id}`);
    load();
  };

  const rangeLabel = `${weekStart.toLocaleDateString(undefined,{month:'short',day:'numeric'})} – ${days[6].toLocaleDateString(undefined,{month:'short',day:'numeric'})}`;
  const shiftWeek = (delta) => { const d = new Date(weekStart); d.setDate(d.getDate() + delta * 7); setWeekStart(d); };

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} data-testid="weekly-plan">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="chip chip-accent mb-3"><CalIcon size={12}/> Weekly plan</div>
          <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tight">This week's shipping plan.</h1>
          <p className="mt-3 text-zinc-400 max-w-xl">Drag any opportunity onto a day. Rearrange to see the flow.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => shiftWeek(-1)} className="btn-ghost text-sm" data-testid="prev-week">← Prev</button>
          <div className="chip">{rangeLabel}</div>
          <button onClick={() => shiftWeek(1)} className="btn-ghost text-sm" data-testid="next-week">Next →</button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2" data-testid="week-grid">
          {days.map((d, i) => {
            const items = planForDay(d);
            const isToday = ymd(d) === ymd(new Date());
            return (
              <div
                key={i}
                onDragOver={(e) => { e.preventDefault(); setDragOver(i); }}
                onDragLeave={() => setDragOver(null)}
                onDrop={() => onDropOnDay(i)}
                data-testid={`day-${i}`}
                className="card-surface p-3 min-h-[280px] flex flex-col transition-colors"
                style={dragOver === i ? { borderColor: 'rgba(138,43,226,0.6)', background: 'rgba(138,43,226,0.06)' } : {}}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">{DAYS[i]}</div>
                    <div className={`font-display text-lg ${isToday ? 'text-violet-300' : 'text-zinc-200'}`}>{d.getDate()}</div>
                  </div>
                  {items.length > 0 && <span className="chip text-[9px]">{items.length}</span>}
                </div>
                <div className="space-y-2 flex-1">
                  {items.map(it => (
                    <div
                      key={it.id}
                      draggable
                      onDragStart={() => setDragging({ type: 'move', planId: it.id })}
                      onDragEnd={() => setDragging(null)}
                      data-testid={`plan-item-${it.id}`}
                      className="p-2 rounded-lg border border-white/10 bg-white/[0.03] cursor-move group"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="chip text-[9px] px-2 mb-1" style={{ borderColor: stageColor(it.opportunity.trend.stage) + '55', color: stageColor(it.opportunity.trend.stage) }}>
                            {it.opportunity.trend.name}
                          </div>
                          <Link to={`/app/opportunity/${it.opportunity_id}`} className="text-xs text-zinc-100 leading-snug line-clamp-2 hover:underline">
                            {it.opportunity.title}
                          </Link>
                        </div>
                        <button onClick={() => removePlan(it.id)} className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400">
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {items.length === 0 && (
                    <div className="h-16 rounded-lg border border-dashed border-white/5 flex items-center justify-center text-[10px] text-zinc-600">
                      drop here
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="card-surface p-4">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-3">Top opportunities · drag onto a day</div>
          <div className="space-y-2" data-testid="plan-source">
            {opps.slice(0, 6).map(o => (
              <div
                key={o.id}
                draggable
                onDragStart={() => setDragging({ type: 'new', oppId: o.id })}
                onDragEnd={() => setDragging(null)}
                data-testid={`source-${o.id}`}
                className="p-3 rounded-lg border border-white/10 bg-white/[0.02] cursor-move hover:border-violet-500/40 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="font-display font-bold text-xl text-white w-9 text-center">{o.score}</div>
                  <div className="flex-1 min-w-0">
                    <div className="chip text-[9px] px-2 mb-1">{o.trend.name}</div>
                    <div className="text-xs text-zinc-100 leading-snug line-clamp-2">{o.title}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-zinc-600 mt-3">Tip: on touch devices, tap and drag slowly.</div>
        </div>
      </div>
    </motion.div>
  );
}
