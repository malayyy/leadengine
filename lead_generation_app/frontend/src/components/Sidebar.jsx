import React, { useState } from 'react';
import { Briefcase, Database, Rocket, Terminal, Cpu, LogOut, Menu, X } from 'lucide-react';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Command Center', icon: Briefcase },
  { key: 'jarvis', label: 'J.A.R.V.I.S', icon: Cpu },
  { key: 'database', label: 'Universal Database', icon: Database },
  { key: 'launch', label: 'Launch Job', icon: Rocket },
];

export default function Sidebar({ activeTab, liveJobId, onNavigate, onLogout }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleNav = (key) => {
    onNavigate(key);
    setMobileOpen(false);
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="p-6 border-b border-white/10 flex items-center space-x-3">
        <div className="w-10 h-10 bg-gradient-to-br from-blue-500/20 to-emerald-500/20 rounded-lg flex items-center justify-center shadow-lg border border-white/10 shrink-0">
          <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-white tracking-tight">LEAD ENGINE</h2>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => handleNav(key)}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === key
                ? key === 'launch' ? 'bg-blue-600/20 text-blue-400 shadow-inner' : 'bg-white/10 text-white shadow-inner'
                : 'hover:bg-white/5 hover:text-white'
            }`}
          >
            <Icon size={18} />
            <span className="font-medium">{label}</span>
          </button>
        ))}
        {liveJobId && (
          <button
            onClick={() => handleNav('live')}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'live' ? 'bg-emerald-600/20 text-emerald-400 shadow-inner' : 'hover:bg-white/5 hover:text-emerald-400'
            }`}
          >
            <Terminal size={18} />
            <span className="font-medium">Live Terminal</span>
          </button>
        )}
      </nav>
      <div className="p-4 border-t border-white/10">
        <button onClick={onLogout} className="w-full text-left px-4 py-2 text-sm text-gray-500 hover:text-white transition-colors uppercase tracking-widest">
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <>
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white/10 backdrop-blur-xl border border-white/10 rounded-xl text-white"
      >
        <Menu size={20} />
      </button>

      <div className="hidden lg:flex w-64 bg-white/5 border-r border-white/10 flex-col backdrop-blur-3xl shrink-0">
        {sidebarContent}
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 bottom-0 w-72 bg-gray-900 border-r border-white/10 shadow-2xl animate-in slide-in-from-left duration-300">
            <button onClick={() => setMobileOpen(false)} className="absolute top-4 right-4 text-gray-400 hover:text-white">
              <X size={20} />
            </button>
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
