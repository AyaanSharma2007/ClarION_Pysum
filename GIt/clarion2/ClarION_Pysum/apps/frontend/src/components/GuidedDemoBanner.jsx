import React from 'react';
import { ArrowRight, X } from 'lucide-react';

const STEPS = [
  { id: 1, label: 'Capture & Parse', role: 'cta_ops', desc: 'PDF intake & Safety Gateway pre-filtering (Bible §6.2)' },
  { id: 2, label: 'Connect & Classify', role: 'cta_ops', desc: 'Local Qwen 2.5 LLM category tagging — zero cloud exposure (Bible §7.1)' },
  { id: 3, label: 'Predict & Recommend', role: 'medical_writing', desc: 'Dual pgvector semantic search + Neo4j structural graph context (Bible §8.5)' },
  { id: 4, label: 'Submission Gate', role: 'ra_clinical', desc: 'Statutory SLA timer & human stage advancement (Bible §6.1)' },
  { id: 5, label: 'Govern & Audit', role: 'executive', desc: 'Cryptographic SHA-256 hash chain verification (Bible §10)' },
];

export default function GuidedDemoBanner({ currentStep, setCurrentStep, setDemoMode, setActiveRole }) {
  return (
    <div className="bg-black border-b border-white/10 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-6">
        <span className="text-[10px] uppercase tracking-widest text-gray-500 font-mono flex-shrink-0">Guided Demo</span>

        <div className="flex items-center space-x-1 overflow-x-auto">
          {STEPS.map((step, i) => {
            const isActive = currentStep === step.id;
            return (
              <React.Fragment key={step.id}>
                <button
                  onClick={() => { setCurrentStep(step.id); setActiveRole(step.role); }}
                  className={`flex-shrink-0 px-3 py-1.5 rounded text-xs font-medium cursor-pointer transition ${
                    isActive ? 'bg-white text-black' : 'text-gray-500 hover:text-white'
                  }`}
                  title={step.desc}
                >
                  {step.id}. {step.label}
                </button>
                {i < STEPS.length - 1 && <ArrowRight className="w-3 h-3 text-gray-700 flex-shrink-0" />}
              </React.Fragment>
            );
          })}
        </div>

        <div className="flex items-center space-x-4 flex-shrink-0">
          <span className="text-[10px] text-gray-600 hidden lg:block">
            {STEPS.find(s => s.id === currentStep)?.desc}
          </span>
          <button onClick={() => setDemoMode(false)} className="text-gray-600 hover:text-white transition cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

