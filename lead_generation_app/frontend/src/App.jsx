import React, { useState, useCallback, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';

import { ToastProvider } from './components/Toast';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import UniversalDatabase from './components/UniversalDatabase';
import LaunchJob from './components/LaunchJob';
import LiveTerminal from './components/LiveTerminal';
import JobDetails from './components/JobDetails';
import Jarvis from './components/Jarvis';

function AppShell({ token, onLogin, onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();

  const activeTab = location.pathname.replace('/', '') || 'dashboard';
  const [liveJobId, setLiveJobId] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);

  const handleNavigate = useCallback((key) => navigate(`/${key}`), [navigate]);
  const handleJobLaunched = useCallback((jobId) => {
    setLiveJobId(jobId);
    navigate('/live');
  }, [navigate]);
  const handleJobSelect = useCallback((jobId) => {
    setSelectedJobId(jobId);
    navigate('/job_details');
  }, [navigate]);

  const headerTitles = {
    dashboard: 'Overview',
    database: 'Database Explorer',
    launch: 'Deployment Setup',
    job_details: `Job #${selectedJobId} Manager`,
    live: 'Live Operations',
    jarvis: 'J.A.R.V.I.S',
  };

  return (
    <div className="min-h-screen flex bg-[#070b14] text-gray-300 font-sans selection:bg-blue-500/30">
      <Sidebar activeTab={activeTab} liveJobId={liveJobId} onNavigate={handleNavigate} onLogout={onLogout} />

      <div className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-[#070b14] to-[#0f172a]">
        <header className="h-16 border-b border-white/10 flex items-center justify-between px-8 bg-black/20 backdrop-blur-md z-10 shrink-0">
          <h1 className="text-xl font-semibold text-white">{headerTitles[activeTab] || 'Lead Engine'}</h1>
        </header>

        <main className="flex-1 overflow-auto p-8 relative">
          {activeTab === 'dashboard' && <Dashboard onJobSelect={handleJobSelect} />}
          {activeTab === 'database' && <UniversalDatabase />}
          {activeTab === 'launch' && <LaunchJob onJobLaunched={handleJobLaunched} />}
          {activeTab === 'live' && <LiveTerminal jobId={liveJobId} />}
          {activeTab === 'jarvis' && <Jarvis />}
          {activeTab === 'job_details' && (
            <JobDetails
              key={selectedJobId}
              jobId={selectedJobId}
              onBack={() => { setSelectedJobId(null); navigate('/dashboard'); }}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('adminToken'));

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    }
  }, [token]);

  const handleLogin = useCallback((newToken) => {
    setToken(newToken);
    localStorage.setItem('adminToken', newToken);
    axios.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    localStorage.removeItem('adminToken');
    delete axios.defaults.headers.common["Authorization"];
  }, []);

  if (!token) return <Login onLogin={handleLogin} />;

  return (
    <ToastProvider>
      <Routes>
        <Route path="/*" element={<AppShell token={token} onLogin={handleLogin} onLogout={handleLogout} />} />
      </Routes>
    </ToastProvider>
  );
}

export default App;
