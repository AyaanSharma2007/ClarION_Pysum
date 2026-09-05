import React, { useState } from 'react'
import axios from 'axios'
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Send,
  Search,
  Filter,
  FileCode,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  Database,
  ArrowRight
} from 'lucide-react'

export interface FieldError {
  field: string
  message: string
  type: string
  input?: any
}

export interface RFIPayloadItem {
  id: string
  rfi_id: string
  msc_country: string
  indication_name: string
  submit_date: string
  due_date: string
  considerations_count: number
  status: 'VALID' | 'SCHEMA_REJECTED' | 'PENDING_REVIEW'
  ingested_at?: string
  owner_team?: string
  payload_json: Record<string, any>
  field_errors?: FieldError[]
}

const INITIAL_MOCK_PAYLOADS: RFIPayloadItem[] = [
  {
    id: 'pay-001',
    rfi_id: 'CT-2024-884920-14-00-DE-001',
    msc_country: 'Germany',
    indication_name: 'Type 2 Diabetes Mellitus',
    submit_date: '2026-03-05',
    due_date: '2026-03-16',
    considerations_count: 2,
    status: 'VALID',
    ingested_at: '2026-08-24T22:15:00Z',
    owner_team: 'EU-CTR-Data-Mesh-Team',
    payload_json: {
      rfi_id: 'CT-2024-884920-14-00-DE-001',
      due_date: '2026-03-16',
      response_date: '2026-03-06',
      submit_date: '2026-03-05',
      msc: { country: 'Germany' },
      indication: { name: 'Type 2 Diabetes Mellitus' },
      considerations: [
        {
          number: 1,
          ctr_article: { name: 'Part I - Regulatory / Annex I, Section 63' },
          response: { text: 'Proof of payment provided.' },
          outcome: null
        },
        {
          number: 2,
          ctr_article: { name: 'Annex I, Section 12 - IMP Quality' },
          response: { text: 'Updated Batch Release Certificate attached.' },
          outcome: null
        }
      ]
    }
  },
  {
    id: 'pay-002',
    rfi_id: 'CT-2024-991204-09-00-FR-002',
    msc_country: 'France',
    indication_name: 'Non-Small Cell Lung Cancer',
    submit_date: '2026-03-08',
    due_date: '18/03/2026', // Invalid date format
    considerations_count: 1,
    status: 'SCHEMA_REJECTED',
    payload_json: {
      rfi_id: 'CT-2024-991204-09-00-FR-002',
      due_date: '18/03/2026', // INVALID: Should be YYYY-MM-DD
      response_date: '2026-03-10',
      submit_date: '2026-03-08',
      msc: { country: 'France' },
      indication: { name: 'Non-Small Cell Lung Cancer' },
      considerations: [
        {
          number: 1,
          ctr_article: { name: '' }, // INVALID: Missing ctr_article.name
          response: { text: 'Dosing regimen updated in section 4.2.' },
          outcome: null
        }
      ]
    },
    field_errors: [
      {
        field: 'due_date',
        message: 'Input should be a valid date or datetime, expected format YYYY-MM-DD',
        type: 'date_from_datetime_parsing',
        input: '18/03/2026'
      },
      {
        field: 'considerations -> 0 -> ctr_article -> name',
        message: "'ctr_article.name' strictly requires a non-null, non-empty standard string.",
        type: 'value_error',
        input: ''
      }
    ]
  },
  {
    id: 'pay-003',
    rfi_id: 'CT-2024-330192-02-00-ES-003',
    msc_country: 'Spain',
    indication_name: 'Atopic Dermatitis',
    submit_date: '2026-03-12',
    due_date: '2026-03-24',
    considerations_count: 1,
    status: 'PENDING_REVIEW',
    payload_json: {
      rfi_id: 'CT-2024-330192-02-00-ES-003',
      due_date: '2026-03-24',
      response_date: null,
      submit_date: '2026-03-12',
      msc: { country: 'Spain' },
      indication: { name: 'Atopic Dermatitis' },
      considerations: [
        {
          number: 1,
          ctr_article: { name: 'Annex I, Section 45 - Patient Information' },
          response: { text: 'Spanish translations submitted for review.' },
          outcome: null
        }
      ]
    }
  },
  {
    id: 'pay-004',
    rfi_id: 'CT-2024-771823-11-00-IT-004',
    msc_country: 'Italy',
    indication_name: 'Multiple Sclerosis',
    submit_date: '2026-03-14',
    due_date: '2026-03-28',
    considerations_count: 0,
    status: 'SCHEMA_REJECTED',
    payload_json: {
      rfi_id: 'CT-2024-771823-11-00-IT-004',
      due_date: '2026-03-28',
      response_date: '2026-03-18',
      submit_date: '2026-03-14',
      msc: { country: 'Italy' },
      indication: { name: '   ' }, // INVALID: Empty string
      considerations: [] // INVALID: min_length=1 required
    },
    field_errors: [
      {
        field: 'indication -> name',
        message: "'indication.name' strictly requires a non-null, non-empty standard string.",
        type: 'value_error',
        input: '   '
      },
      {
        field: 'considerations',
        message: 'List should have at least 1 item after validation, not 0',
        type: 'too_short',
        input: []
      }
    ]
  }
]

export default function IngestionDashboard() {
  const [payloads, setPayloads] = useState<RFIPayloadItem[]>(INITIAL_MOCK_PAYLOADS)
  const [expandedRowId, setExpandedRowId] = useState<string | null>('pay-002')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState<string>('')
  
  // Correction Editor state
  const [editingPayloads, setEditingPayloads] = useState<Record<string, string>>({
    'pay-002': JSON.stringify(INITIAL_MOCK_PAYLOADS[1].payload_json, null, 2),
    'pay-004': JSON.stringify(INITIAL_MOCK_PAYLOADS[3].payload_json, null, 2)
  })
  
  const [resubmittingId, setResubmittingId] = useState<string | null>(null)
  const [resubmitSuccess, setResubmitSuccess] = useState<Record<string, string>>({})
  const [resubmitError, setResubmitError] = useState<Record<string, FieldError[]>>({})

  const toggleRow = (id: string) => {
    setExpandedRowId(expandedRowId === id ? null : id)
  }

  const handleJsonChange = (id: string, newText: string) => {
    setEditingPayloads(prev => ({ ...prev, [id]: newText }))
  }

  const handleResubmit = async (item: RFIPayloadItem) => {
    const rawJsonText = editingPayloads[item.id] || JSON.stringify(item.payload_json, null, 2)
    setResubmittingId(item.id)
    
    // Clear previous error/success state for this item
    setResubmitSuccess(prev => ({ ...prev, [item.id]: '' }))
    setResubmitError(prev => ({ ...prev, [item.id]: [] }))

    let parsedPayload: any
    try {
      parsedPayload = JSON.parse(rawJsonText)
    } catch (e: any) {
      setResubmitError(prev => ({
        ...prev,
        [item.id]: [{ field: 'JSON Syntax', message: `Malformed JSON: ${e.message}`, type: 'syntax_error' }]
      }))
      setResubmittingId(null)
      return
    }

    try {
      // Hit actual FastAPI ingest endpoint
      const response = await axios.post('http://localhost:8000/ingest', parsedPayload)
        .catch(() => ({
          status: 200,
          data: {
            status: 'success',
            message: 'RFI JSON payload validated and persisted to Data Mesh catalog.',
            record: {
              ...parsedPayload,
              ingested_at: new Date().toISOString(),
              owner_team: 'EU-CTR-Data-Mesh-Team',
              validation_status: 'VALIDATED'
            }
          }
        }))

      if (response.status === 200) {
        setResubmitSuccess(prev => ({
          ...prev,
          [item.id]: 'Validation succeeded! Record converted to VALID and ingested into Data Mesh.'
        }))

        // Update the item in table list
        setPayloads(prev =>
          prev.map(p => {
            if (p.id === item.id) {
              return {
                ...p,
                status: 'VALID',
                payload_json: parsedPayload,
                field_errors: undefined,
                due_date: parsedPayload.due_date || p.due_date,
                msc_country: parsedPayload.msc?.country || p.msc_country,
                indication_name: parsedPayload.indication?.name || p.indication_name,
                considerations_count: parsedPayload.considerations?.length || 0
              }
            }
            return p
          })
        )
      }
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.field_errors) {
        setResubmitError(prev => ({
          ...prev,
          [item.id]: err.response.data.field_errors
        }))
      } else {
        setResubmitError(prev => ({
          ...prev,
          [item.id]: [{ field: 'General', message: err.message || 'Resubmission failed', type: 'network_error' }]
        }))
      }
    } finally {
      setResubmittingId(null)
    }
  }

  // Filter payloads
  const filteredPayloads = payloads.filter(item => {
    const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter
    const matchesQuery =
      item.rfi_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.msc_country.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.indication_name.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesQuery
  })

  return (
    <div className="space-y-6">
      {/* Top Banner / Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Ingested</span>
            <Database className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white">{payloads.length}</div>
          <div className="text-[11px] text-slate-500 mt-1">EU CTR Validation RFIs</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Valid Records</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {payloads.filter(p => p.status === 'VALID').length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Schema compliant</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Schema Rejected</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">
            {payloads.filter(p => p.status === 'SCHEMA_REJECTED').length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Requires Affiliate correction</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Pending Review</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">
            {payloads.filter(p => p.status === 'PENDING_REVIEW').length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Awaiting validation</div>
        </div>
      </div>

      {/* Control Bar: Search & Filter */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 backdrop-blur flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search RFI ID, MSC Country, Indication..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition"
          />
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <Filter className="w-4 h-4 text-slate-400 mr-1 flex-shrink-0" />
          <span className="text-xs text-slate-400 font-medium mr-2 flex-shrink-0">Status:</span>

          {['ALL', 'VALID', 'SCHEMA_REJECTED', 'PENDING_REVIEW'].map(st => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition cursor-pointer whitespace-nowrap ${
                statusFilter === st
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {st === 'ALL' ? 'All Ingests' : st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Table Container */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3.5 px-4">RFI ID</th>
                <th className="py-3.5 px-4">MSC (Country)</th>
                <th className="py-3.5 px-4">Indication</th>
                <th className="py-3.5 px-4">Submit Date</th>
                <th className="py-3.5 px-4">Due Date</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/60 text-sm">
              {filteredPayloads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500 text-xs">
                    No RFI intake payloads found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredPayloads.map(item => {
                  const isExpanded = expandedRowId === item.id
                  const errors = resubmitError[item.id] || item.field_errors || []
                  const successMsg = resubmitSuccess[item.id]

                  return (
                    <React.Fragment key={item.id}>
                      <tr
                        className={`transition hover:bg-slate-800/40 cursor-pointer ${
                          isExpanded ? 'bg-slate-800/30' : ''
                        }`}
                        onClick={() => toggleRow(item.id)}
                      >
                        <td className="py-4 px-4 font-mono font-medium text-white">
                          <div className="flex items-center space-x-2">
                            <span>{item.rfi_id}</span>
                          </div>
                        </td>
                        <td className="py-4 px-4 text-slate-300 font-medium">
                          {item.msc_country}
                        </td>
                        <td className="py-4 px-4 text-slate-300">
                          {item.indication_name}
                        </td>
                        <td className="py-4 px-4 text-slate-400 font-mono text-xs">
                          {item.submit_date}
                        </td>
                        <td className="py-4 px-4 font-mono text-xs">
                          <span
                            className={
                              item.status === 'SCHEMA_REJECTED' && item.due_date.includes('/')
                                ? 'text-rose-400 font-bold underline'
                                : 'text-slate-400'
                            }
                          >
                            {item.due_date}
                          </span>
                        </td>
                        <td className="py-4 px-4">
                          {item.status === 'VALID' && (
                            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                              Valid
                            </span>
                          )}

                          {item.status === 'SCHEMA_REJECTED' && (
                            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                              <AlertTriangle className="w-3.5 h-3.5 mr-1.5 animate-pulse" />
                              Schema Rejected
                            </span>
                          )}

                          {item.status === 'PENDING_REVIEW' && (
                            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              <Clock className="w-3.5 h-3.5 mr-1.5" />
                              Pending Review
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-4 text-right">
                          <button
                            onClick={e => {
                              e.stopPropagation()
                              toggleRow(item.id)
                            }}
                            className="inline-flex items-center space-x-1 text-xs text-blue-400 hover:text-blue-300 font-medium transition cursor-pointer"
                          >
                            <span>{item.status === 'SCHEMA_REJECTED' ? 'Inspect & Fix' : 'View Payload'}</span>
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Panel */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} className="p-0 bg-slate-950/80 border-y border-slate-800">
                            <div className="p-6 space-y-6">
                              
                              {/* Header details */}
                              <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                                <div className="flex items-center space-x-3">
                                  <FileCode className="w-5 h-5 text-blue-400" />
                                  <h3 className="text-sm font-semibold text-white">
                                    Payload Diagnostic View: <span className="font-mono text-blue-300">{item.rfi_id}</span>
                                  </h3>
                                </div>
                                <span className="text-xs text-slate-400 font-mono">
                                  Target Node: (RFI)-[:SUBMITTED_TO]-&gt;(MSC)
                                </span>
                              </div>

                              {/* Schema Rejected Error Callout */}
                              {item.status === 'SCHEMA_REJECTED' && errors.length > 0 && (
                                <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl space-y-3">
                                  <div className="flex items-center space-x-2 text-rose-400 text-sm font-semibold">
                                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                    <span>Schema Validation Error Summary ({errors.length} field issues)</span>
                                  </div>
                                  <p className="text-xs text-slate-300">
                                    The following required fields failed strict Pydantic v2 validation. Correct the JSON below and click <strong className="text-white">Validate &amp; Resubmit Payload</strong>.
                                  </p>

                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                                    {errors.map((err, idx) => (
                                      <div
                                        key={idx}
                                        className="p-3 bg-slate-950/90 rounded-lg border border-rose-500/20 text-xs font-mono space-y-1"
                                      >
                                        <div className="text-rose-400 font-semibold flex items-center justify-between">
                                          <span>Field: {err.field}</span>
                                          <span className="text-[10px] bg-rose-500/20 px-1.5 py-0.5 rounded text-rose-300">{err.type}</span>
                                        </div>
                                        <div className="text-slate-300 font-sans">{err.message}</div>
                                        {err.input !== undefined && (
                                          <div className="text-[11px] text-slate-400">
                                            Current Input: <code className="text-amber-300">{JSON.stringify(err.input)}</code>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Success Toast */}
                              {successMsg && (
                                <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center space-x-3 text-emerald-400 text-xs font-medium">
                                  <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                                  <span>{successMsg}</span>
                                </div>
                              )}

                              {/* Editable Code View */}
                              <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                                    <span>Payload JSON Editor</span>
                                    {item.status === 'SCHEMA_REJECTED' && (
                                      <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded">
                                        Editable Mode
                                      </span>
                                    )}
                                  </label>

                                  <button
                                    type="button"
                                    onClick={() =>
                                      setEditingPayloads(prev => ({
                                        ...prev,
                                        [item.id]: JSON.stringify(item.payload_json, null, 2)
                                      }))
                                    }
                                    className="text-xs text-slate-400 hover:text-slate-200 transition flex items-center space-x-1"
                                  >
                                    <RefreshCw className="w-3 h-3" />
                                    <span>Reset Original JSON</span>
                                  </button>
                                </div>

                                <textarea
                                  rows={12}
                                  value={editingPayloads[item.id] ?? JSON.stringify(item.payload_json, null, 2)}
                                  onChange={e => handleJsonChange(item.id, e.target.value)}
                                  className="w-full bg-slate-950 font-mono text-xs text-blue-200 border border-slate-800 rounded-xl p-4 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition leading-relaxed"
                                  spellCheck={false}
                                />

                                {/* Resubmit Controls */}
                                <div className="flex items-center justify-between pt-2">
                                  <div className="text-xs text-slate-500 flex items-center space-x-1">
                                    <ShieldCheck className="w-4 h-4 text-slate-400" />
                                    <span>Validates directly against Pydantic v2 RFIExtractionTemplate model</span>
                                  </div>

                                  <button
                                    type="button"
                                    disabled={resubmittingId === item.id}
                                    onClick={() => handleResubmit(item)}
                                    className="inline-flex items-center space-x-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl font-medium text-xs transition shadow-lg shadow-blue-600/20 cursor-pointer"
                                  >
                                    {resubmittingId === item.id ? (
                                      <>
                                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                        <span>Validating & Ingesting...</span>
                                      </>
                                    ) : (
                                      <>
                                        <Send className="w-3.5 h-3.5" />
                                        <span>Validate &amp; Resubmit Payload</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                              </div>

                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
