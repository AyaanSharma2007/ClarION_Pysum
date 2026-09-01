import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import RaClinicalView from './components/RaClinicalView';
import CtaOpsView from './components/CtaOpsView';
import MedicalWritingView from './components/MedicalWritingView';
import ExecutiveView from './components/ExecutiveView';
import GuidedDemoModal from './components/GuidedDemoModal';
import { checkSystemHealth } from './services/api';

const RFIS = [
  {
    rfi_uuid: 'CT-2026-QWEN-TEST-001',
    rfi_id: 'CT-2026-QWEN-TEST-001',
    msc_country: 'Denmark',
    indication_name: 'Immunology',
    category: 'IMPD Safety',
    stage: 'RA_Clinical_Review',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Annex I, Section 63' },
      response: { text: 'IMPD Section 2.1 safety documentation and toxicological assay reporting updated.' },
    }],
  },
  {
    rfi_uuid: 'CT-2024-884920-14-DE-001',
    rfi_id: 'CT-2024-884920-14-DE-001',
    msc_country: 'Germany',
    indication_name: 'Type 2 Diabetes',
    category: 'Statistics',
    stage: 'Received',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 30 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Part I – Regulatory / Annex I, Section 63' },
      response: { text: 'Statistical power calculation and sample size justification section 4.2 updated.' },
    }],
  },
  {
    rfi_uuid: 'CT-2024-991204-09-FR-002',
    rfi_id: 'CT-2024-991204-09-FR-002',
    msc_country: 'France',
    indication_name: 'Oncology',
    category: 'Protocol Design',
    stage: 'CTA_Mgmt_Review',
    sla_status: 'ACTIVE',
    due_date: new Date(Date.now() + 12 * 3600 * 1000).toISOString(),
    considerations: [{
      ctr_article: { name: 'Annex I, Section 12 – IMP Quality' },
      response: { text: 'Batch release specification and dosage regimen details updated.' },
    }],
  },
];

export default function App() {
  const [role, setRole] = useState('ra_clinical');
  const [health, setHealth] = useState({ layer1: false, layer2: false, ollama: false });
  const [showDemo, setShowDemo] = useState(false);

  useEffect(() => {
    const poll = async () => setHealth(await checkSystemHealth());
    poll();
    const t = setInterval(poll, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', display: 'flex', flexDirection: 'column' }}>
      <Header
        activeRole={role}
        setActiveRole={setRole}
        systemHealth={health}
        onOpenDemo={() => setShowDemo(true)}
      />

      <main style={{ flex: 1, maxWidth: 1280, width: '100%', margin: '0 auto', padding: '0 24px' }}>
        {role === 'ra_clinical'     && <RaClinicalView rfis={RFIS} onRefresh={() => {}} />}
        {role === 'cta_ops'         && <CtaOpsView onRefresh={() => {}} />}
        {role === 'medical_writing' && <MedicalWritingView />}
        {role === 'executive'       && <ExecutiveView rfis={RFIS} />}
      </main>

      {showDemo && (
        <GuidedDemoModal onClose={() => setShowDemo(false)} setActiveRole={setRole} />
      )}
    </div>
  );
}
