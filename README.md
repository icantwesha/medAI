# Patient AI Record System

Supabase (database) + FastAPI (backend) + Groq (Qwen chatbot with tool use) + plain HTML frontend.

The frontend supports patient search, patient creation/edit/deletion, visit and prescription recording, appointment scheduling/status updates, and a read-only AI assistant. This is a local demo for fictional data, not a production clinical records system. The API URL is configured in the `api-base` meta tag in `index.html`.

## How the chatbot works
1. User asks a question in the chat box.
2. Backend sends it to Groq along with 4 tools (search patients, get history, find by diagnosis, list appointments).
3. The model picks a read-only tool, the backend runs the matching Supabase query, and returns the rows to the model.
4. The model writes a concise answer based on those rows. It may provide general educational information and topics to discuss with a licensed clinician, but must not diagnose, prescribe, or advise medication changes. The backend appends a consistent disclaimer.

## Demo features
- Search and refresh patient records; create, edit, and delete patients.
- Select gender from the form; optional phone numbers accept 7–15 digits (with optional international `+` and common separators) and are validated by both the browser and API.
- View the visit history and prescriptions for a patient, and add new visits or prescription records.
- Schedule appointments and update their status.
- Ask the read-only assistant questions about patient records, diagnosis history, and appointments.
- Chat responses and patient summaries include source chips built from records actually returned by Supabase.
- Summarize an open patient record with Groq; the model is prompted to summarize only supplied record data.
- Use optional browser speech recognition to dictate a chat prompt where supported; review the transcript before sending.
- Review a record-completeness percentage based on whether selected demographic fields and visit history are documented. It is not a medical-risk score.

These management features use the existing tables in `schema.sql`; no additional SQL migration is needed if you already ran that script.

## Setup
1. Create a project at [supabase.com](https://supabase.com). In the project, open **SQL Editor > New query**, paste the contents of `schema.sql`, and run it. This creates the patient, visit, prescription, and appointment tables and inserts demo records. You do not need to create the tables separately.
2. Copy `.env.example` to `.env` in this project directory. Fill in the Supabase project URL, the service-role key (Project Settings > API), and your Groq API key. The default model is `qwen/qwen3.8-27b`; change `MODEL` in `.env` if needed. Keep `.env` private; never put these keys in `index.html`.
3. From this project directory, install dependencies and start the backend:
   ```
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```
4. Open `index.html` in a browser. If the backend runs at a different address, update the `api-base` meta tag near the top of `index.html`.

To change the demo records, edit and rerun the relevant `insert` statements in `schema.sql`, or use the Supabase **Table Editor** after creating the schema. For an already-created database, run only new/updated insert statements to avoid duplicating the sample rows.

## Notes for your report
- API keys stay in the backend; the browser never sees them.
- Use fictional data only; patient record context sent in assistant requests goes to Groq.
- This demo has no sign-in, role-based access, audit trail, or production privacy controls. Do not deploy it for real patient data.
- The backend currently uses a Supabase service-role key, which bypasses row-level security. Keep the backend private and never expose that key in frontend code.
- Before any real deployment, add authentication/authorization, least-privilege database access, audit logging, secure hosting, data retention controls, and an appropriate privacy/compliance review.
