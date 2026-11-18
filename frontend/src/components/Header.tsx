import React from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, actions }) => {
  return (
    <header className="bg-[#111821]/80 backdrop-blur-sm border-b border-white/8 px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-20">
      <div>
        <h1 className="text-lg font-semibold text-[#F4F7FA] tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-[#98A5B5] mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <Link
          to="/new"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#36D6A0] text-[#0B0F14] text-xs font-semibold hover:bg-[#2ec290] transition-colors"
        >
          <PlusCircle className="w-4 h-4" />
          New Analysis
        </Link>
      </div>
    </header>
  );
};
