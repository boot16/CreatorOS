import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import './lib/client'; // side-effect: install X-Client-Id header
import DemoBadge from './components/DemoBadge';
import { useBootstrap } from './lib/bootstrap';

import Landing from './pages/Landing';
import Onboarding from './pages/Onboarding';
import DNAReveal from './pages/DNAReveal';
import DNADashboard from './pages/DNADashboard';
import OpportunityFeed from './pages/OpportunityFeed';
import OpportunityDetail from './pages/OpportunityDetail';
import TrendRadar from './pages/TrendRadar';
import TrendDetail from './pages/TrendDetail';
import IdeaLab from './pages/IdeaLab';
import CreatorProfile from './pages/CreatorProfile';
import Shortlist from './pages/Shortlist';
import Studio from './pages/Studio';
import ScriptsList from './pages/ScriptsList';
import ScriptEditor from './pages/ScriptEditor';
import Projects from './pages/Projects';
import ProjectWorkspace from './pages/ProjectWorkspace';
import Layout from './components/Layout';

function AppShell({ children }) {
  const boot = useBootstrap();
  const loc = useLocation();
  // Real signed-in user with no DNA yet → force onboarding once before entering the app.
  if (!boot.loading && boot.is_authenticated && !boot.onboarding_complete && loc.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="dark" position="top-right" toastOptions={{
        style: { background: '#12121A', border: '1px solid rgba(255,255,255,0.1)', color: '#F8F9FA' },
      }} />
      <DemoBadge />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dna-reveal" element={<DNAReveal />} />

        <Route path="/app" element={<AppShell><Projects /></AppShell>} />
        <Route path="/app/projects/:id" element={<AppShell><ProjectWorkspace /></AppShell>} />
        <Route path="/app/feed" element={<AppShell><OpportunityFeed /></AppShell>} />
        <Route path="/app/dna" element={<AppShell><DNADashboard /></AppShell>} />
        <Route path="/app/opportunity/:id" element={<AppShell><OpportunityDetail /></AppShell>} />
        <Route path="/app/trends" element={<AppShell><TrendRadar /></AppShell>} />
        <Route path="/app/trends/:id" element={<AppShell><TrendDetail /></AppShell>} />
        <Route path="/app/idea/:oppId" element={<AppShell><IdeaLab /></AppShell>} />
        <Route path="/app/collab" element={<AppShell><CreatorProfile /></AppShell>} />
        <Route path="/app/shortlist" element={<AppShell><Shortlist /></AppShell>} />
        <Route path="/app/studio" element={<AppShell><Studio /></AppShell>} />
        <Route path="/app/scripts" element={<AppShell><ScriptsList /></AppShell>} />
        <Route path="/app/scripts/:id" element={<AppShell><ScriptEditor /></AppShell>} />

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
