-- Run this in Supabase: SQL Editor > New query > paste > Run
create table patients (
  id bigint generated always as identity primary key,
  name text not null,
  dob date,
  gender text,
  phone text,
  blood_group text,
  allergies text default 'None'
);

create table visits (
  id bigint generated always as identity primary key,
  patient_id bigint references patients(id) on delete cascade,
  doctor_name text,
  visit_date date,
  symptoms text,
  diagnosis text,
  notes text
);

create table prescriptions (
  id bigint generated always as identity primary key,
  visit_id bigint references visits(id) on delete cascade,
  medicine text,
  dosage text,
  duration text
);

create table appointments (
  id bigint generated always as identity primary key,
  patient_id bigint references patients(id) on delete cascade,
  doctor_name text,
  appt_time timestamptz,
  status text default 'scheduled'
);

-- Dummy data only (never use real patient data in a demo)
insert into patients (name, dob, gender, phone, blood_group, allergies) values
 ('Asha Verma','1985-03-12','F','9000000001','B+','Penicillin'),
 ('Ravi Kumar','1972-11-02','M','9000000002','O+','None'),
 ('Meena Iyer','1993-07-21','F','9000000003','A+','Sulfa drugs');

insert into visits (patient_id, doctor_name, visit_date, symptoms, diagnosis, notes) values
 (1,'Dr. Rao','2026-08-10','Fatigue, thirst','Type 2 Diabetes','HbA1c 8.1, start metformin'),
 (1,'Dr. Rao','2026-09-15','Follow-up','Type 2 Diabetes','HbA1c 7.2, improving'),
 (2,'Dr. Sen','2026-09-01','Chest tightness','Hypertension','BP 150/95, lifestyle advice'),
 (3,'Dr. Rao','2026-09-20','Cough, fever','Viral bronchitis','Rest, fluids');

insert into prescriptions (visit_id, medicine, dosage, duration) values
 (1,'Metformin','500mg twice daily','3 months'),
 (3,'Amlodipine','5mg once daily','1 month'),
 (4,'Paracetamol','500mg as needed','5 days');

insert into appointments (patient_id, doctor_name, appt_time, status) values
 (1,'Dr. Rao','2026-10-12 10:00+05:30','scheduled'),
 (2,'Dr. Sen','2026-10-09 15:30+05:30','scheduled'),
 (3,'Dr. Rao','2026-09-27 11:00+05:30','completed');
