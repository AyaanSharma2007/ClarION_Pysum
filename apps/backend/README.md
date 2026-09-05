# RFI Nexus Backend Service

FastAPI service powering the RFI Nexus Data Mesh Intake pipeline. Integrates with Anthropic LLM for metadata schema extraction and Supabase for database & data mesh persistence.

## Tech Stack
- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Validation**: Pydantic
- **AI Extraction**: Anthropic API (`anthropic`)
- **Database / Backend-as-a-Service**: Supabase (`supabase`)

## Setup & Execution

1. Navigate to the backend directory:
   ```bash
   cd apps/backend
   ```

2. Create & activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your ANTHROPIC_API_KEY, SUPABASE_URL, and SUPABASE_KEY
   ```

5. Run the dev server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
