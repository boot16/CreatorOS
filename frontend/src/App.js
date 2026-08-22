import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import './lib/client'; // side-effect: install X-Client-Id header

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
import Layout from './components/Layout';

function AppShell({ children }) { return <Layout>{children}</Layout>; }

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="dark" position="top-right" toastOptions={{
        style: { background: '#12121A', border: '1px solid rgba(255,255,255,0.1)', color: '#F8F9FA' },
      }} />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dna-reveal" element={<DNAReveal />} />

        <Route path="/app" element={<AppShell><OpportunityFeed /></AppShell>} />
        <Route path="/app/dna" element={<AppShell><DNADashboard /></AppShell>} />
        <Route path="/app/opportunity/:id" element={<AppShell><OpportunityDetail /></AppShell>} />
        <Route path="/app/trends" element={<AppShell><TrendRadar /></AppShell>} />
        <Route path="/app/trends/:id" element={<AppShell><TrendDetail /></AppShell>} />
        <Route path="/app/idea/:oppId" element={<AppShell><IdeaLab /></AppShell>} />
        <Route path="/app/collab" element={<AppShell><CreatorProfile /></AppShell>} />
        <Route path="/app/shortlist" element={<AppShell><Shortlist /></AppShell>} />
        <Route path="/app/studio" element={<AppShell><Studio /></AppShell>} />

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
