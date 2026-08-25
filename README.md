# RFI Nexus Data Mesh Intake

Monorepo workspace for **RFI Nexus Data Mesh Intake** — an automated system for ingesting, validating, schema-extracting, and cataloging Request for Information (RFI) datasets across enterprise Data Mesh domains.

---

## 🏗️ Workspace Architecture

```
ClarION_Pysum/
├── package.json           # Root monorepo workspace configuration
├── README.md              # Project documentation & guidelines
├── schemas/               # Shared JSON Schema definitions for RFI intake
│   ├── rfi_extraction_schema.json
│   └── rfi_extraction_example.json
└── apps/
    ├── backend/           # FastAPI service (Python)
    │   ├── main.py        # FastAPI API application & endpoints
    │   ├── requirements.txt # Dependencies: fastapi, uvicorn, pydantic, anthropic, supabase
    │   ├── README.md
    │   └── .env.example
    └── frontend/          # React + Vite application (JavaScript / JSX)
        ├── package.json   # Dependencies: lucide-react, axios, react-hook-form, tailwindcss
        ├── vite.config.js # Vite + Tailwind CSS configuration
        ├── tailwind.config.js
        └── src/
            ├── App.jsx    # Interactive RFI Intake Portal component
            └── index.css  # Tailwind CSS base styles
```

---

## ⚡ Quick Start

### 1. Root Workspace Commands
From the repository root:
- **Run Frontend**: `npm run dev:frontend`
- **Build Frontend**: `npm run build:frontend`
- **Run Backend**: `npm run dev:backend`

### 2. Frontend Setup (`apps/frontend`)
```bash
cd apps/frontend
npm install
npm run dev
```

### 3. Backend Setup (`apps/backend`)
```bash
cd apps/backend
pip install -r requirements.txt
uvicorn main:app --reload
```

---

## 📦 Installed Tech Stack & Dependencies

### `apps/backend/requirements.txt`
- `fastapi` — High performance web framework for APIs
- `uvicorn` — Lightning-fast ASGI server implementation
- `pydantic` — Data validation and schema management
- `anthropic` — Anthropic Claude SDK for AI schema extraction
- `supabase` — Supabase Python Client for Data Mesh registry persistence

### `apps/frontend/package.json`
- `tailwindcss` & `@tailwindcss/vite` — Utility-first CSS framework
- `lucide-react` — Icon set
- `axios` — HTTP client for backend API communication
- `react-hook-form` — Performant form state management & validation
