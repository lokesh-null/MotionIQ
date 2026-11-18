import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { AnalysisResultsPage } from './pages/AnalysisResults';
import { Dashboard } from './pages/Dashboard';
import { NewAnalysis } from './pages/NewAnalysis';
import { Processing } from './pages/Processing';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0B0F14] text-[#F4F7FA] flex">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/new" element={<NewAnalysis />} />
            <Route path="/processing/:id" element={<Processing />} />
            <Route path="/results/:id" element={<AnalysisResultsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
};

export default App;
