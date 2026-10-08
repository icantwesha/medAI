# MedAI — Patient Records & AI Assistant

MedAI is a full-stack patient-record management demo that brings patient profiles, visit history, prescriptions, and appointments together in one clean dashboard. Its AI assistant can look up records through read-only database tools, answer questions with record-based context, and summarize a selected patient's documented history.

Built with **FastAPI**, **Supabase**, and **Groq**, MedAI is designed to demonstrate how an AI layer can make structured records easier to explore—not replace clinical judgment.

> **Demo project:** Use fictional data only. MedAI is not a clinical product and is not suitable for real patient information or care decisions.

## What you can do

- **Manage patient records:** search, add, edit, and delete patient profiles.
- **Track care history:** review visits and prescriptions, and record new visits or prescriptions.
- **Coordinate appointments:** schedule appointments and update their status.
- **Ask questions in natural language:** find patients, explore documented diagnoses, look up visit history, and list appointments through the AI assistant.
- **See the evidence:** assistant answers and patient summaries can show source chips identifying the database records used.
- **Summarize a patient record:** request a concise AI-generated summary of a patient's recorded details and visits.
- **Use voice input:** dictate a prompt in supported browsers, then review it before sending.
- **Check record completeness:** see whether selected demographic fields and visit history are documented. This is a documentation indicator, not a medical-risk score.
- **Use the dashboard your way:** responsive layout, light/dark theme, and database-backed forms.

## How the AI assistant works

1. The browser sends the question and conversation history to the FastAPI backend.
2. For record-specific questions, Groq can select from read-only tools for patient search, patient history, diagnosis lookup, and appointments.
3. The backend runs the selected query against Supabase and returns its results to the model.
4. The assistant writes a concise response using those results. The interface displays source chips derived from records returned by the tools—not sources invented by the model.

The assistant can provide general educational information, but it must not diagnose, prescribe, recommend medication changes, or create a personalized treatment plan. Record summaries are generated from supplied database records.

## Technology

| Layer | Technology |
| --- | --- |
| User interface | HTML, CSS, and JavaScript |
| API | Python and FastAPI |
| Database | Supabase (PostgreSQL) |
| AI | Groq API with a configurable chat-completion model |

## Get started

### Requirements

- Python 3.10 or newer
- A [Supabase](https://supabase.com/) project
- A [Groq API key](https://console.groq.com/keys)

### 1. Create the database

In your Supabase project, open **SQL Editor → New query**, paste in [`schema.sql`](./schema.sql), and run it once. It creates the patients, visits, prescriptions, and appointments tables and inserts fictional sample records.

If you have already run the schema, do not run the full script again: it creates tables and inserts sample rows. Use Supabase's **Table Editor** to manage existing records, or run only the specific SQL statements you need.

### 2. Configure credentials

Copy `.env.example` to `.env` in the project directory, then set:

```dotenv
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
GROQ_API_KEY=your-groq-api-key
MODEL=qwen/qwen3.8-27b
```

Get the Supabase URL and service-role key from your project's API settings. The model can be changed using `MODEL` if your Groq account supports a different model.

**Keep `.env` private.** Never commit it, share its contents, or put API keys in frontend code. The service-role key has elevated database access and must remain on the backend.

### 3. Install dependencies and start the API

From the project directory, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

The API root (`/`) serves the dashboard, and `/health` returns a small health response for deployment checks. When opened locally, the dashboard uses `http://localhost:8000`; when served by the deployed API, it automatically uses the same origin. If you host the frontend separately, set the `api-base` meta tag near the top of `index.html` to your API's public HTTPS URL.

### 4. Open the app

For local development, open `index.html` in a browser while the API is running. Alternatively, visit `http://127.0.0.1:8000/` to load the dashboard directly from FastAPI.

## Project layout

```text
.
├── index.html       # Dashboard and browser-side application
├── main.py          # FastAPI routes, Supabase access, and Groq integration
├── schema.sql       # Database schema and fictional seed data
├── requirements.txt # Python dependencies
└── .env.example     # Credential template (copy to .env)
```

## Important limitations

- This is a local demonstration, **not a production patient-record system**.
- Use fictional data only. Patient information sent to AI features is processed by Groq; review the provider's terms and data policies before using any service.
- The backend uses a Supabase service-role key, which bypasses row-level security. Never expose the key to the browser or an untrusted user.
- The demo does not implement user sign-in, role-based permissions, audit logging, production-grade privacy controls, or clinical validation.
- Browser speech recognition depends on browser support, permissions, and the browser's speech service.
- The record-completeness indicator only reflects the presence of selected fields. It is not an ML model, diagnosis, or risk estimate.

Before adapting this project for real-world use, design and implement authentication and authorization, least-privilege database access, audit logging, secure deployment, data-retention controls, and an appropriate privacy, security, and regulatory review.
