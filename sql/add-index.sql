-- Fix for the slow search: index the column used in the WHERE clause
CREATE INDEX IF NOT EXISTS idx_person_email ON person (email);
ANALYZE person;
