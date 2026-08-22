import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Sparkles, Radar, Lightbulb, Users } from 'lucide-react';

const links = [
  { to: '/app', label: 'Feed', icon: Sparkles, end: true },
  { to: '/app/trends', label: 'Trends', icon: Radar },
  { to: '/app/dna', label: 'Creator DNA', icon: Lightbulb },
  { to: '/app/collab', label: 'Collab', icon: Users },
];

export default function Layout({ children }) {
  const loc = useLocation();
  return (
    <div className="min-h-screen">
      <header
        className="sticky top-0 z-40 backdrop-blur-xl border-b border-white/10"
        style={{ background: 'rgba(10,10,15,0.72)' }}
      >
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/app" data-testid="brand-link" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
            <span className="font-display text-lg font-semibold tracking-tight">CreatorOS</span>
          </Link>
          <nav className="hidden md:flex items-center gap-1">
            {links.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to} to={to} end={end}
                data-testid={`nav-${label.toLowerCase().replace(' ','-')}`}
                className={({ isActive }) =>
                  `px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 ${
                    isActive ? 'bg-white/5 text-white' : 'text-zinc-400 hover:text-white'
                  }`}
              >
                <Icon size={14} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden md:inline text-xs text-zinc-500">Demo · Alex Morgan</span>
            <div className="w-8 h-8 rounded-full" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
          </div>
        </div>
      </header>
      <main key={loc.pathname} className="max-w-7xl mx-auto px-6 py-10">
        {children}
      </main>
      <footer className="max-w-7xl mx-auto px-6 py-10 text-xs text-zinc-600">
        CreatorOS · demo build · seeded data, live LLM
      </footer>
    </div>
  );
}
