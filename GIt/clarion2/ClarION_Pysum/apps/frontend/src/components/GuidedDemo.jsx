import React, { useState } from 'react';

const steps = [
  { title: "Capture", desc: "Data mesh ingestion. The PDF is parsed and OPA/Safety Gateways are checked." },
  { title: "Connect", desc: "Layer 3 Knowledge Graph. Finding patterns across MSCs and Indications." },
  { title: "Predict", desc: "Layer 4 Risk Engine. Surfacing predictive risk for the RFI with SHAP." },
  { title: "Recommend", desc: "Layer 5 Recommender. Re-ranking past successes using hybrid search." },
  { title: "Govern", desc: "Layer 6 Orchestration. Submission Gate, hash-chain audit, ALCOA+ checks." }
];

const GuidedDemo = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-full shadow-lg z-50 transition-all"
      >
        Open Guided Demo Mode
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-slate-900/95 backdrop-blur-md border border-emerald-500/30 rounded-xl shadow-2xl z-50 overflow-hidden flex flex-col">
      <div className="bg-emerald-900/50 p-4 border-b border-emerald-500/20 flex justify-between items-center">
        <h3 className="text-emerald-400 font-bold tracking-wide">Guided Demo Mode</h3>
        <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white">&times;</button>
      </div>
      
      <div className="p-6 flex-grow">
        <h4 className="text-2xl font-bold text-white mb-2">{steps[activeStep].title}</h4>
        <p className="text-slate-300 text-sm leading-relaxed min-h-[60px]">
          {steps[activeStep].desc}
        </p>
        
        <div className="flex space-x-2 mt-6">
          {steps.map((_, idx) => (
            <div key={idx} className={`h-1 flex-1 rounded-full ${idx === activeStep ? 'bg-emerald-400' : idx < activeStep ? 'bg-emerald-800' : 'bg-slate-700'}`} />
          ))}
        </div>
      </div>
      
      <div className="p-4 bg-slate-800 flex justify-between items-center">
        <button 
          disabled={activeStep === 0}
          onClick={() => setActiveStep(prev => prev - 1)}
          className="px-3 py-1 text-sm text-slate-400 disabled:opacity-50 hover:text-white"
        >
          Previous
        </button>
        <button 
          onClick={() => {
            if (activeStep < steps.length - 1) setActiveStep(prev => prev + 1);
            else setIsOpen(false);
          }}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded shadow transition-colors"
        >
          {activeStep === steps.length - 1 ? "Finish Demo" : "Next Step"}
        </button>
      </div>
    </div>
  );
};

export default GuidedDemo;
