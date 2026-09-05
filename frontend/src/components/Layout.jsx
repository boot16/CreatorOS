import React, { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Sparkles, Radar, Lightbulb, Users, Bookmark, MessageSquare, FileText, LayoutGrid, LogOut, User as UserIcon } from 'lucide-react';
import { useShortlist } from '../lib/shortlist';
import { useBootstrap, logout } from '../lib/bootstrap';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuLabel,
} from './ui/dropdown-menu';

const links = [
  { to: '/app', label: 'Projects', icon: LayoutGrid, end: true },
  { to: '/app/feed', label: 'Feed', icon: Sparkles },
  { to: '/app/trends', label: 'Trends', icon: Radar },
  { to: '/app/dna', label: 'DNA', icon: Lightbulb },
  { to: '/app/studio', label: 'Studio', icon: MessageSquare },
  { to: '/app/scripts', label: 'Scripts', icon: FileText },
  { to: '/app/shortlist', label: 'Saved', icon: Bookmark, badge: true },
  { to: '/app/collab', label: 'Collab', icon: Users },
];

export default function Layout({ children }) {
  const loc = useLocation();
  const nav = useNavigate();
  const { count } = useShortlist();
  const boot = useBootstrap();
  const displayName = boot.user?.name || boot.creator?.display_name || boot.creator?.name || 'Creator';
  const displayEmail = boot.user?.email;
  const initials = (displayName || '?').split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase();
  const modeLabel = boot.is_demo ? 'Demo' : (boot.is_authenticated ? 'Signed in' : '');

  const doLogout = async () => {
    await logout();
    nav('/', { replace: true });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 backdrop-blur-xl border-b border-white/10" style={{ background: 'rgba(10,10,15,0.72)' }}>
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/app" data-testid="brand-link" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg" style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }} />
            <span className="font-display text-lg font-semibold tracking-tight">CreatorOS</span>
          </Link>
          <nav className="hidden md:flex items-center gap-1">
            {links.map(({ to, label, icon: Icon, end, badge }) => (
              <NavLink
                key={to} to={to} end={end}
                data-testid={`nav-${label.toLowerCase().replace(' ','-')}`}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-full text-sm font-medium flex items-center gap-2 ${
                    isActive ? 'bg-white/5 text-white' : 'text-zinc-400 hover:text-white'
                  }`}
              >
                <Icon size={14} />
                {label}
                {badge && count > 0 && (
                  <span className="ml-1 px-1.5 h-5 min-w-[20px] rounded-full text-[10px] font-mono flex items-center justify-center bg-violet-500 text-white">
                    {count}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden md:inline text-xs text-zinc-500" data-testid="user-mode-label">
              {modeLabel}{modeLabel && ' · '}{displayName}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  data-testid="user-menu-trigger"
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border border-white/10"
                  style={{ background: 'linear-gradient(135deg,#8A2BE2,#4C1D95)' }}
                >
                  {initials}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="border-white/10" style={{ background: '#12121A' }}>
                <DropdownMenuLabel>
                  <div className="text-sm font-medium">{displayName}</div>
                  {displayEmail && <div className="text-xs text-zinc-500">{displayEmail}</div>}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {boot.is_authenticated ? (
                  <DropdownMenuItem onClick={doLogout} data-testid="logout-btn">
                    <LogOut size={14} className="mr-2" /> Log out
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem onClick={() => (window.location.href = '/')} data-testid="signin-btn">
                    <UserIcon size={14} className="mr-2" /> Sign in
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main key={loc.pathname} className="max-w-7xl mx-auto px-6 py-10">
        {children}
      </main>
      <footer className="max-w-7xl mx-auto px-6 py-10 text-xs text-zinc-600">
        CreatorOS · {boot.is_demo ? 'demo build · seeded data' : 'your workspace'} · live LLM
      </footer>
    </div>
  );
}
