import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, LayoutDashboard, PlusCircle, ShieldCheck } from 'lucide-react';

export const Sidebar: React.FC = () => {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-[#36D6A0]/12 text-[#36D6A0] border border-[#36D6A0]/30'
        : 'text-[#98A5B5] hover:text-[#F4F7FA] hover:bg-[#161F2B]'
    }`;

  return (
    <aside className="w-full md:w-64 shrink-0 bg-[#111821] border-b md:border-b-0 md:border-r border-white/8 flex flex-col justify-between md:min-h-screen md:sticky md:top-0 z-30">
      <div>
        {/* Brand + Mobile Quick Nav */}
        <div className="px-4 md:px-5 py-3.5 md:py-5 border-b border-white/8 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#36D6A0]/15 border border-[#36D6A0]/40 flex items-center justify-center text-[#36D6A0]">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="text-base font-bold tracking-tight text-[#F4F7FA]">MOTIONIQ</div>
              <div className="text-[11px] uppercase tracking-wider text-[#98A5B5]">Sports Biomechanics</div>
            </div>
          </div>

          {/* Mobile compact nav pills */}
          <div className="flex md:hidden items-center gap-1.5">
            <NavLink to="/" end className={linkClass}>
              <LayoutDashboard className="w-4 h-4" />
              <span className="text-xs">Home</span>
            </NavLink>
            <NavLink to="/new" className={linkClass}>
              <PlusCircle className="w-4 h-4" />
              <span className="text-xs">Analyze</span>
            </NavLink>
          </div>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden md:block p-4 space-y-1.5">
          <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#98A5B5]/70">
            Workspace
          </div>
          <NavLink to="/" end className={linkClass}>
            <LayoutDashboard className="w-4 h-4" />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/new" className={linkClass}>
            <PlusCircle className="w-4 h-4" />
            <span>New Analysis</span>
          </NavLink>
        </nav>

        {/* Supported Modules Summary (Desktop) */}
        <div className="hidden md:block px-4 py-3">
          <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-[#98A5B5]/70">
            Active CV Engines
          </div>
          <div className="bg-[#161F2B] border border-white/6 rounded-lg p-3 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-[#F4F7FA]">MediaPipe Pose</span>
              <span className="font-mono text-[#36D6A0]">33 Landmarks</span>
            </div>
            <div className="flex items-center justify-between text-[#98A5B5]">
              <span>Squat & Lunge</span>
              <span className="text-[#36D6A0]">Core</span>
            </div>
            <div className="flex items-center justify-between text-[#98A5B5]">
              <span>Jumping Jack</span>
              <span className="text-[#36D6A0]">Core</span>
            </div>
            <div className="flex items-center justify-between text-[#98A5B5]">
              <span>Basketball Shot</span>
              <span className="text-[#F4B860]">Experimental</span>
            </div>
          </div>
        </div>
      </div>

      {/* Prototype Scientific Honesty Footer (Desktop) */}
      <div className="hidden md:block p-4 border-t border-white/8">
        <div className="bg-[#0B0F14] border border-white/6 rounded-lg p-3 text-[11px] text-[#98A5B5] leading-relaxed flex gap-2.5">
          <ShieldCheck className="w-4 h-4 text-[#36D6A0] shrink-0 mt-0.5" />
          <div>
            <span className="text-[#F4F7FA] font-medium block mb-0.5">Educational Prototype</span>
            2D monocular kinematics. Not a clinically validated medical diagnostic device.
          </div>
        </div>
      </div>
    </aside>
  );
};
