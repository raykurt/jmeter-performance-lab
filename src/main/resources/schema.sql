-- The table is created without an index on email on purpose:
-- the first JMeter run measures the slow version, then sql/add-index.sql adds the index.
CREATE TABLE IF NOT EXISTS person (
    id         BIGINT PRIMARY KEY,
    first_name VARCHAR(50)  NOT NULL,
    last_name  VARCHAR(50)  NOT NULL,
    email      VARCHAR(120) NOT NULL,
    city       VARCHAR(50)  NOT NULL,
    created_at TIMESTAMP    NOT NULL
);

-- Seeds 1,000,000 rows only when the table is empty (fast, done inside PostgreSQL)
INSERT INTO person (id, first_name, last_name, email, city, created_at)
SELECT g,
       'First' || g,
       'Last' || (g % 5000),
       'user' || g || '@example.com',
       (ARRAY['Ankara', 'Istanbul', 'Izmir', 'Bursa', 'Antalya'])[1 + g % 5],
       TIMESTAMP '2024-01-01' + (g % 700) * INTERVAL '1 day'
FROM generate_series(1, 1000000) AS g
WHERE NOT EXISTS (SELECT 1 FROM person);

-- New rows created through POST /api/persons get ids after the seeded data
CREATE SEQUENCE IF NOT EXISTS person_id_seq START WITH 1000001;

ANALYZE person;
