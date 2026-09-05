import React from 'react';
import EvidenceIntegrityPanel from './EvidenceIntegrityPanel';

const RoleDashboard = ({ role }) => {
  // Mock Data for the panel
  const mockIntegrityData = {
    dimensions: {
      "Attributable": true,
      "Legible": true,
      "Contemporaneous": true,
      "Original": true,
      "Accurate": true,
      "Complete": true,
      "Consistent": true,
      "Enduring": true,
      "Available": true
    },
    verified: true,
    status: "VERIFIED BY CLARION CHECKS"
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-8">
      <header className="mb-8 border-b border-slate-800 pb-4">
        <h1 className="text-3xl font-light tracking-tight">Clarion <span className="font-bold text-emerald-400">{role}</span> Dashboard</h1>
        <p className="text-slate-500 mt-2">EU CTR Regulatory Memory & Assurance Platform</p>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="col-span-2 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4 text-white">Recent RFIs</h2>
            <div className="space-y-4">
              <div className="p-4 bg-slate-800/50 rounded-lg flex justify-between items-center border border-slate-700/50">
                <div>
                  <div className="font-mono text-emerald-400 text-sm">CT-2026-981244-12-00</div>
                  <div className="text-slate-300 font-medium mt-1">Germany • Type 2 Diabetes</div>
                </div>
                <div className="bg-emerald-900/30 text-emerald-400 px-3 py-1 rounded text-sm font-semibold border border-emerald-800/50">
                  Awaiting Response
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4 text-white">Intelligence & Recommendations</h2>
            <div className="p-4 bg-slate-800/50 border border-slate-700/50 rounded-lg">
              <div className="text-sm text-slate-400 mb-2 font-mono">hybrid_search() top result</div>
              <p className="text-slate-300">"Prior response submitted to Germany for Type 2 Diabetes was accepted with zero follow-ups. Similarity: 95%, Success Score: 98%."</p>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <EvidenceIntegrityPanel data={mockIntegrityData} />
          
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4 text-white">Submission Gate</h2>
            <div className="space-y-3">
              <button className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-medium transition-colors">Request Approval</button>
              <button className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium transition-colors opacity-50 cursor-not-allowed">Submit to CTIS</button>
              <p className="text-xs text-center text-rose-400 mt-2">GATE-001: Approval required before submission.</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default RoleDashboard;
