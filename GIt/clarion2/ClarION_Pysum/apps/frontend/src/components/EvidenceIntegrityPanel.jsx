import React from 'react';

const EvidenceIntegrityPanel = ({ data }) => {
  if (!data) return null;
  
  const { dimensions, verified, status } = data;
  
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 my-4 text-slate-200 font-mono shadow-xl">
      <h3 className="text-xl font-bold mb-4 text-emerald-400 border-b border-slate-700 pb-2">Evidence Integrity Check</h3>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2">
        {Object.entries(dimensions).map(([key, passed]) => (
          <div key={key} className="flex justify-between items-center py-1 border-b border-slate-800/50">
            <span className="text-slate-400">{key}</span>
            {passed ? (
              <span className="text-emerald-500 font-bold">✓</span>
            ) : (
              <span className="text-rose-500 font-bold">✗</span>
            )}
          </div>
        ))}
      </div>
      <div className={`mt-6 p-3 rounded-md text-center font-bold tracking-wider ${verified ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-800' : 'bg-rose-900/30 text-rose-400 border border-rose-800'}`}>
        Result: {status}
      </div>
    </div>
  );
};

export default EvidenceIntegrityPanel;
