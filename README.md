# JMeter Performance Lab

![Performance Tests](https://github.com/raykurt/jmeter-performance-lab/actions/workflows/performance.yml/badge.svg)

A small **Spring Boot + PostgreSQL** service with **1,000,000 rows**, used as a target for **Apache JMeter** load tests.
The pipeline finds a real bottleneck, fixes it, and proves the fix with numbers, for both reads and writes:

1. Load test the API → the email search is slow
2. Check the query plan → PostgreSQL scans the whole table (`Seq Scan`)
3. Add an index on `email` → the plan becomes an `Index Scan`
4. Load test again → compare Average, Median, P90, P95, P99, throughput and error rate
5. Measure the **cost of the index on writes** with a separate POST test
6. A **performance gate** fails the build if P95 goes above the limit

Everything runs in **GitHub Actions** on every push.

## What it shows

- **JMeter test plan** with two thread groups (readers and writers), parameters (`-Jreaders`, `-Jwriters`, `-Jduration`, `-Jhost`, `-Jport`), random test data and response assertions
- **Separate read and write tests**, so one workload does not distort the other
- **Warm-up run** before measuring, so JVM start-up does not distort the results
- **Before/after comparison** of the same scenarios, with HTML dashboards for every run
- **Percentile-based analysis** (P90/P95/P99), not only averages
- **Performance gate in CI**: P95 of each request must stay under 200 ms after the fix
- **Root cause analysis** at the database level with `EXPLAIN ANALYZE`

## Results

Measured in GitHub Actions. Read test: 10 users. Write test: 5 users. 5 s ramp-up, 30 s per run.
Full JMeter HTML dashboards are in the `jmeter-reports` artifact of each [run](https://github.com/raykurt/jmeter-performance-lab/actions).

| Request | Run | Samples | Avg (ms) | P90 | P95 | P99 | Throughput (req/s) | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Search person by email | Before index | 1,026 | 267 | 453 | **480** | 521 | 34.1 | 0% |
| Search person by email | After index | 132,382 | 1 | 2 | **2** | 3 | 4,421.6 | 0% |
| Get person by id | Before index | 1,016 | 4 | 8 | 11 | 15 | 34.0 | 0% |
| Get person by id | After index | 132,379 | 1 | 2 | 2 | 2 | 4,425.3 | 0% |
| Create person (POST) | Before index | 82,133 | 2 | 1 | 2 | 14 | 2,744.4 | 0% |
| Create person (POST) | After index | 79,497 | 2 | 1 | 2 | 18 | 2,655.6 | 0% |

**Takeaways**

- **Reads:** email search P95 dropped from **480 ms to 2 ms** (about 240x faster), and read throughput grew from **34 to about 4,400 requests per second** (about 130x).
- **One slow endpoint limited the whole system:** the fast `Get person by id` request was also stuck at 34 req/s before the fix, because each reader runs both requests in a loop.
- **Writes:** the index has a small cost. Every insert also updates the index, so write throughput dropped by **about 3%** (2,744 → 2,656 req/s) and P99 went from 14 ms to 18 ms, while P95 stayed at 2 ms.
- **Trade-off:** a huge gain on reads for a small cost on writes. For a read-heavy system, this index is clearly worth it.
- The performance gate (P95 < 200 ms after the fix) passed for all three requests.

> Note: write latencies are only a few milliseconds, so JMeter's 1 ms resolution makes small differences look large in percentages. Throughput is the more reliable signal for the write cost.

## Query plan

```sql
EXPLAIN ANALYZE
SELECT id, first_name, last_name, email, city, created_at FROM person WHERE email = 'user777777@example.com';
```

- **Before:** `Parallel Seq Scan on person`, every request reads the whole table, and requests queue up under load
- **After** (`CREATE INDEX idx_person_email ON person (email)`): `Index Scan using idx_person_email`, a single lookup

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/persons?email=...` | Search by email (slow without the index) |
| GET | `/api/persons/{id}` | Primary key lookup (baseline) |
| POST | `/api/persons` | Create a person, returns `201 Created` (`400` if a field is missing) |

## Project structure

```
src/main/java/com/raykurt/perflab/   Spring Boot app (controller, repository, request/response records)
src/main/resources/schema.sql        creates the table and sequence, seeds 1,000,000 rows (no email index on purpose)
sql/add-index.sql                    the fix
jmeter/person-api-load.jmx           JMeter test plan (Readers and Writers thread groups)
scripts/summarize.py                 percentiles, before/after tables, performance gate
.github/workflows/performance.yml    build, start app, warm-up, read/write tests before and after the index, compare
docker-compose.yml                   PostgreSQL for local runs
```

## Run locally

```bash
docker compose up -d                       # PostgreSQL
mvn spring-boot:run                        # app on http://localhost:8080 (first start seeds the data)

jmeter -n -t jmeter/person-api-load.jmx -l results/read-before.jtl  -Jreaders=10 -Jwriters=0
jmeter -n -t jmeter/person-api-load.jmx -l results/write-before.jtl -Jreaders=0  -Jwriters=5
psql -h localhost -U perflab -d perflab -f sql/add-index.sql     # password: perflab
jmeter -n -t jmeter/person-api-load.jmx -l results/read-after.jtl   -Jreaders=10 -Jwriters=0
jmeter -n -t jmeter/person-api-load.jmx -l results/write-after.jtl  -Jreaders=0  -Jwriters=5

python3 scripts/summarize.py \
  --run "Before index=results/read-before.jtl,results/write-before.jtl" \
  --run "After index=results/read-after.jtl,results/write-after.jtl"
```

To run again without the index: `DROP INDEX idx_person_email;`

## Related projects

- [api-test-automation-framework](https://github.com/raykurt/api-test-automation-framework) – API tests with Java, REST Assured and Cucumber
- [playwright-typescript-ui-tests](https://github.com/raykurt/playwright-typescript-ui-tests) – UI tests with Playwright and TypeScript
- [cypress-cucumber-ui-tests](https://github.com/raykurt/cypress-cucumber-ui-tests) – UI tests with Cypress, Cucumber and TypeScript
