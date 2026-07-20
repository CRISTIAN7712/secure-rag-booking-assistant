CREATE TABLE IF NOT EXISTS appointment_services (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS professionals (
    id UUID PRIMARY KEY,
    service_id UUID NOT NULL REFERENCES appointment_services(id),
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS appointment_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (ends_at > starts_at),
    UNIQUE(professional_id, starts_at)
);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_id UUID NOT NULL REFERENCES appointment_slots(id),
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at TIMESTAMPTZ
);

ALTER TABLE appointments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS appointment_conversations (
    session_id UUID PRIMARY KEY,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_appointment_per_slot
ON appointments(slot_id) WHERE status = 'confirmed';
CREATE INDEX IF NOT EXISTS idx_appointment_slots_start ON appointment_slots(starts_at);
CREATE INDEX IF NOT EXISTS idx_appointments_customer_email
ON appointments(lower(customer_email), status);

INSERT INTO appointment_services(id, name, description, duration_minutes) VALUES
('10000000-0000-0000-0000-000000000001', 'Soporte técnico', 'Diagnóstico y solución de problemas técnicos.', 30),
('10000000-0000-0000-0000-000000000002', 'Demostración comercial', 'Demostración guiada de la plataforma.', 60),
('10000000-0000-0000-0000-000000000003', 'Consultoría', 'Sesión de asesoría para implementación y mejores prácticas.', 60)
ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name, description=EXCLUDED.description,
duration_minutes=EXCLUDED.duration_minutes, active=TRUE;

INSERT INTO professionals(id, service_id, name) VALUES
('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'Laura Gómez'),
('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'Carlos Ruiz'),
('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000003', 'Ana Torres')
ON CONFLICT(id) DO UPDATE SET service_id=EXCLUDED.service_id, name=EXCLUDED.name, active=TRUE;

-- Genera horarios simulados para los próximos 45 días laborables en Bogotá.
INSERT INTO appointment_slots(professional_id, starts_at, ends_at)
SELECT p.id,
       ((day::date + hour_value * interval '1 hour') AT TIME ZONE 'America/Bogota'),
       ((day::date + hour_value * interval '1 hour' + s.duration_minutes * interval '1 minute') AT TIME ZONE 'America/Bogota')
FROM professionals p
JOIN appointment_services s ON s.id = p.service_id
CROSS JOIN generate_series(current_date, current_date + 45, interval '1 day') AS day
CROSS JOIN (VALUES (9), (11), (14), (16)) AS hours(hour_value)
WHERE EXTRACT(ISODOW FROM day) BETWEEN 1 AND 5
ON CONFLICT(professional_id, starts_at) DO NOTHING;
