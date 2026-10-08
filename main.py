import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from supabase import create_client
from groq import Groq

load_dotenv()
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
ai = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.getenv("MODEL", "qwen/qwen3.8-27b")

app = FastAPI(title="Patient AI Record System")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def normalize_phone(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Phone number must be text.")
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"\+?[0-9][0-9(). -]*", value):
        raise ValueError("Enter a phone number using digits and optional spaces, parentheses, hyphens, or a leading +.")
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        raise ValueError("Phone number must contain 7 to 15 digits.")
    return ("+" if value.startswith("+") else "") + digits


class PatientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    dob: date | None = None
    gender: Literal["F", "M", "Non-binary", "Prefer not to say"] | None = None
    phone: str | None = Field(default=None, max_length=40)
    blood_group: str | None = Field(default=None, max_length=8)
    allergies: str | None = Field(default=None, max_length=1000)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        return normalize_phone(value)


class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=160)
    dob: date | None = None
    gender: Literal["F", "M", "Non-binary", "Prefer not to say"] | None = None
    phone: str | None = Field(default=None, max_length=40)
    blood_group: str | None = Field(default=None, max_length=8)
    allergies: str | None = Field(default=None, max_length=1000)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        return normalize_phone(value)

    @model_validator(mode="after")
    def name_cannot_be_cleared(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Patient name cannot be empty.")
        return self


class VisitInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    doctor_name: str | None = Field(default=None, max_length=160)
    visit_date: date = Field(default_factory=date.today)
    symptoms: str | None = Field(default=None, max_length=2000)
    diagnosis: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


class PrescriptionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    medicine: str = Field(min_length=1, max_length=200)
    dosage: str | None = Field(default=None, max_length=200)
    duration: str | None = Field(default=None, max_length=200)


class AppointmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    patient_id: int = Field(gt=0)
    doctor_name: str | None = Field(default=None, max_length=160)
    appt_time: datetime
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"


class AppointmentStatusUpdate(BaseModel):
    status: Literal["scheduled", "completed", "cancelled"]


# ---------- DB helper functions the chatbot can call ----------
def search_patients(name: str):
    return (db.table("patients")
            .select("id, name, dob, gender, phone, blood_group, allergies")
            .ilike("name", f"%{name}%").limit(20).execute().data)

def get_patient_history(patient_id: int):
    patient = (db.table("patients")
              .select("id, name, dob, gender, blood_group, allergies")
              .eq("id", patient_id).limit(1).execute().data)
    visits = (db.table("visits").select("*, prescriptions(*)")
              .eq("patient_id", patient_id).order("visit_date", desc=True).execute().data)
    return {"patient": patient, "visits": visits}

def find_by_diagnosis(keyword: str):
    return (db.table("visits").select("id, visit_date, diagnosis, patients(id, name)")
            .ilike("diagnosis", f"%{keyword}%").execute().data)

def list_appointments(status: str = "scheduled"):
    return (db.table("appointments").select("*, patients(name)")
            .eq("status", status).order("appt_time").execute().data)

FUNCS = {f.__name__: f for f in (search_patients, get_patient_history, find_by_diagnosis, list_appointments)}


def _source_date(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "Date not recorded"
    try:
        return date.fromisoformat(value[:10]).strftime("%d %b %Y")
    except ValueError:
        return "Date not recorded"


def _tool_sources(tool_name: str, result: object) -> list[dict[str, str | int]]:
    sources: list[dict[str, str | int]] = []

    def add(kind: str, record_id: object, label: str) -> None:
        if isinstance(record_id, (int, str)):
            sources.append({"kind": kind, "id": record_id, "label": label})

    if tool_name == "search_patients" and isinstance(result, list):
        for patient in result:
            if isinstance(patient, dict):
                add("patient", patient.get("id"), f"Patient record · {patient.get('name', 'Patient')}")
    elif tool_name == "get_patient_history" and isinstance(result, dict):
        patients = result.get("patient", [])
        patient = patients[0] if isinstance(patients, list) and patients else None
        patient_name = patient.get("name", "Patient") if isinstance(patient, dict) else "Patient"
        if isinstance(patient, dict):
            add("patient", patient.get("id"), f"Patient record · {patient_name}")
        visits = result.get("visits", [])
        if isinstance(visits, list):
            for visit in visits:
                if isinstance(visit, dict):
                    add("visit", visit.get("id"),
                        f"Visit · {_source_date(visit.get('visit_date'))}")
    elif tool_name == "find_by_diagnosis" and isinstance(result, list):
        for visit in result:
            if isinstance(visit, dict):
                patient = visit.get("patients")
                patient_name = patient.get("name", "Patient") if isinstance(patient, dict) else "Patient"
                add("visit", visit.get("id"),
                    f"{patient_name} · Visit · {_source_date(visit.get('visit_date'))}")
    elif tool_name == "list_appointments" and isinstance(result, list):
        for appointment in result:
            if isinstance(appointment, dict):
                patient = appointment.get("patients")
                patient_name = patient.get("name", "Patient") if isinstance(patient, dict) else "Patient"
                add("appointment", appointment.get("id"),
                    f"{patient_name} · Appointment · {_source_date(appointment.get('appt_time'))}")

    unique: dict[tuple[str, str], dict[str, str | int]] = {}
    for source in sources:
        unique[(str(source["kind"]), str(source["id"]))] = source
    return list(unique.values())


def _patient_sources(patient: dict, visits: list[dict]) -> list[dict[str, str | int]]:
    sources = _tool_sources("get_patient_history", {"patient": [patient], "visits": visits})
    return sources


def summarize_patient_records(patient: dict, visits: list[dict]) -> str:
    records = json.dumps({"patient": patient, "visits": visits}, default=str)
    try:
        response = ai.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize this fictional patient record for administrative demonstration only. "
                        "Use only the supplied JSON. Separate recorded facts from missing information. "
                        "Do not diagnose, prescribe, or recommend starting, stopping, or changing treatment. "
                        "Use concise bullets and dates. State that this is a record summary, not clinical advice."
                    ),
                },
                {"role": "user", "content": records},
            ],
            max_completion_tokens=700,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="The AI service request failed while summarizing this patient.") from error
    return add_records_disclaimer(
        response.choices[0].message.content or "The model returned an empty summary."
    )

TOOLS = [
    {"type": "function", "function": {
        "name": "search_patients", "description": "Find patients by (partial) name.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "get_patient_history", "description": "Get a patient's details, visits and prescriptions by patient id.",
        "parameters": {"type": "object", "properties": {"patient_id": {"type": "integer"}}, "required": ["patient_id"]}}},
    {"type": "function", "function": {
        "name": "find_by_diagnosis", "description": "Find visits/patients whose diagnosis contains a keyword (e.g. diabetes).",
        "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "list_appointments", "description": "List appointments by status: scheduled, completed or cancelled.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string"}}}}},
]

SYSTEM = (
    "You are a read-only assistant for a fictional patient-record demo. "
    "For patient-specific or appointment questions, use the database tools and answer only from their results. "
    "Never invent records or imply that missing data exists. Say when a result is unavailable. "
    "You may offer brief, general educational information and non-urgent topics the patient could discuss with "
    "their licensed clinician, using the recorded condition only as context. Clearly separate facts found in "
    "the record from general information. Do not diagnose, prescribe, recommend starting/stopping/changing "
    "medications, give a personalized treatment plan, or present yourself as a clinician. For urgent or "
    "worsening symptoms, tell the user to contact local emergency services or a qualified clinician promptly. "
    "Keep answers concise, mention relevant dates, and do not add a disclaimer because the application adds one. "
    "Today is " + date.today().isoformat() + "."
)
RECORDS_DISCLAIMER = (
    "General information only—not a diagnosis or treatment plan. A qualified clinician should guide care for the patient."
)


def add_records_disclaimer(reply: str) -> str:
    if RECORDS_DISCLAIMER.casefold() in reply.casefold():
        return reply
    separator = "\n\n" if reply else ""
    return f"{reply}{separator}{RECORDS_DISCLAIMER}"

# ---------- API ----------
@app.api_route("/", methods=["GET", "HEAD"])
def dashboard():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/health")
def health_check():
    return {"status": "ok", "service": app.title}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)

@app.post("/chat")
def chat(body: ChatIn):
    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend(message.model_dump() for message in body.history)
    messages.append({"role": "user", "content": body.message})
    sources: list[dict[str, str | int]] = []
    for _ in range(6):  # max tool-call rounds
        try:
            response = ai.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_completion_tokens=1000,
            )
        except Exception as error:
            raise HTTPException(status_code=502, detail="The AI service request failed. Check Groq configuration and try again.") from error
        assistant_message = response.choices[0].message
        if not assistant_message.tool_calls:
            return {"reply": add_records_disclaimer(assistant_message.content or ""), "sources": sources}

        messages.append(assistant_message.model_dump(exclude_none=True))
        for tool_call in assistant_message.tool_calls:
            function = tool_call.function
            if function.name not in FUNCS:
                result = {"error": f"Unknown tool: {function.name}"}
            else:
                try:
                    arguments = json.loads(function.arguments)
                except json.JSONDecodeError as error:
                    raise HTTPException(status_code=502, detail="The model returned invalid tool arguments.") from error
                try:
                    result = FUNCS[function.name](**arguments)
                except Exception as error:
                    raise HTTPException(status_code=500, detail="A database lookup for the assistant failed.") from error
                sources.extend(_tool_sources(function.name, result))
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })
    raise HTTPException(status_code=502, detail="The model exceeded the maximum number of tool-call rounds.")

@app.get("/patients")
def patients():
    return (db.table("patients")
            .select("id, name, dob, gender, phone, blood_group, allergies")
            .order("name").execute().data)


@app.post("/patients", status_code=201)
def create_patient(body: PatientInput):
    data = body.model_dump(mode="json")
    return db.table("patients").insert(data).execute().data[0]


@app.get("/patients/{patient_id}")
def patient_detail(patient_id: int):
    patient = (db.table("patients").select("*")
               .eq("id", patient_id).limit(1).execute().data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    visits = (db.table("visits").select("*, prescriptions(*)")
              .eq("patient_id", patient_id).order("visit_date", desc=True).execute().data)
    return {"patient": patient[0], "visits": visits}


@app.post("/patients/{patient_id}/summary")
def patient_summary(patient_id: int):
    patient = (db.table("patients")
               .select("id, name, dob, gender, blood_group, allergies")
               .eq("id", patient_id).limit(1).execute().data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    visits = (db.table("visits")
              .select("id, doctor_name, visit_date, symptoms, diagnosis, notes, prescriptions(id, medicine, dosage, duration)")
              .eq("patient_id", patient_id).order("visit_date", desc=True).execute().data)
    summary = add_records_disclaimer(summarize_patient_records(patient[0], visits))
    return {
        "summary": summary,
        "sources": _patient_sources(patient[0], visits),
    }


@app.put("/patients/{patient_id}")
def update_patient(patient_id: int, body: PatientUpdate):
    changes = body.model_dump(exclude_unset=True, mode="json")
    if not changes:
        raise HTTPException(status_code=400, detail="Provide at least one field to update.")
    updated = (db.table("patients").update(changes)
               .eq("id", patient_id).execute().data)
    if not updated:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return updated[0]


@app.delete("/patients/{patient_id}", status_code=204)
def delete_patient(patient_id: int):
    deleted = db.table("patients").delete().eq("id", patient_id).execute().data
    if not deleted:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return Response(status_code=204)


@app.post("/patients/{patient_id}/visits", status_code=201)
def create_visit(patient_id: int, body: VisitInput):
    patient = (db.table("patients").select("id")
               .eq("id", patient_id).limit(1).execute().data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    data = body.model_dump(mode="json")
    data["patient_id"] = patient_id
    return db.table("visits").insert(data).execute().data[0]


@app.post("/visits/{visit_id}/prescriptions", status_code=201)
def create_prescription(visit_id: int, body: PrescriptionInput):
    visit = (db.table("visits").select("id")
             .eq("id", visit_id).limit(1).execute().data)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found.")
    data = body.model_dump()
    data["visit_id"] = visit_id
    return db.table("prescriptions").insert(data).execute().data[0]


@app.get("/appointments")
def appointments():
    return (db.table("appointments").select("id, patient_id, doctor_name, appt_time, status, patients(name)")
            .order("appt_time").execute().data)


@app.post("/appointments", status_code=201)
def create_appointment(body: AppointmentInput):
    patient = (db.table("patients").select("id")
               .eq("id", body.patient_id).limit(1).execute().data)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    data = body.model_dump(mode="json")
    return db.table("appointments").insert(data).execute().data[0]


@app.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: int, body: AppointmentStatusUpdate):
    updated = (db.table("appointments").update(body.model_dump())
               .eq("id", appointment_id).execute().data)
    if not updated:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return updated[0]


# Run: uvicorn main:app --reload
