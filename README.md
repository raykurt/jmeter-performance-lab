# JMeter Performance Lab

![Performance Tests](https://github.com/raykurt/jmeter-performance-lab/actions/workflows/performance.yml/badge.svg)

A small **Spring Boot + PostgreSQL** service with **1,000,000 rows**, used as a target for **Apache JMeter** load tests.
The pipeline finds a real bottleneck, fixes it, and proves the fix with numbers, for reads, writes and a full user journey:

1. Load test the API → the email search is slow
2. Check the query plan → PostgreSQL scans the whole table (`Seq Scan`)
3. Add an index on `email` → the plan becomes an `Index Scan`
4. Load test again → compare Average, Median, P90, P95, P99, throughput and error rate
5. Measure the **cost of the index on writes** with a separate POST test
6. Run a **user journey with correlation**: create a person, extract the id from the response, then read and search it
7. **Performance gates** fail the build if P95 or the error rate goes above the limit

Everything runs in **GitHub Actions** on every push.

## What it shows

- **JMeter test plan** with three thread groups (readers, writers, journey users) and parameters (`-Jreaders`, `-Jwriters`, `-Jjourney`, `-Jduration`, `-Jhost`, `-Jport`)
- **Correlation**: a JSON Extractor saves `id` and `email` from the POST response and the next requests use them
- **Test data from CSV** (`CSV Data Set Config`), random data with `__Random` and `__UUID`
- **Think time** between journey steps (300–700 ms) and a **Transaction Controller** that measures the whole journey
- **Assertions**: status codes, response body, and JSON Path checks that the API returns the record we created
- **Separate read and write tests**, so one workload does not distort the other
- **Warm-up run**, **before/after comparison** and HTML dashboards for every run
- **Percentile-based analysis** (P90/P95/P99), not only averages
- **Performance gates in CI**: P95 limits and a 0% error-rate gate for the journey
- **Reliable pipeline**: JMeter is cached, with a fallback download source and timeouts
- **Root cause analysis** at the database level with `EXPLAIN ANALYZE`

## Results

Measured in GitHub Actions. Read test: 10 users. Write test: 5 users. Journey: 5 users with think time. 30 s per run.
Full JMeter HTML dashboards are in the `jmeter-reports` artifact of each [run](https://github.com/raykurt/jmeter-performance-lab/actions).

### Reads and writes, before and after the index

| Request | Run | Samples | Avg (ms) | P90 | P95 | P99 | Throughput (req/s) | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Search person by email | Before index | 729 | 376 | 647 | **697** | 801 | 24.2 | 0% |
| Search person by email | After index | 90,354 | 1 | 2 | **3** | 4 | 3,021.2 | 0% |
| Get person by id | Before index | 719 | 5 | 10 | 12 | 16 | 24.1 | 0% |
| Get person by id | After index | 90,351 | 1 | 2 | 3 | 4 | 3,024.9 | 0% |
| Create person (POST) | Before index | 117,175 | 1 | 2 | 2 | 4 | 3,917.7 | 0% |
| Create person (POST) | After index | 118,093 | 1 | 2 | 2 | 3 | 3,948.5 | 0% |

### User journey with correlation (after index)

| Step | Samples | Avg (ms) | P95 | P99 | Errors |
|---|---:|---:|---:|---:|---:|
| 1. Create person (POST, extract `id` and `email`) | 139 | 2 | 3 | 3 | 0% |
| 2. Get created person by extracted `id` | 137 | 2 | 2 | 3 | 0% |
| 3. Search created person by extracted `email` | 134 | 2 | 3 | 3 | 0% |
| **Whole journey (transaction, without think time)** | 137 | 5 | **7** | 8 | **0%** |

**Takeaways**

- **Reads:** email search P95 dropped from **697 ms to 3 ms** (about 230x faster), and read throughput grew from **24 to about 3,000 requests per second**.
- **One slow endpoint limited the whole system:** the fast `Get person by id` request was also stuck at 24 req/s before the fix, because each reader runs both requests in a loop.
- **Writes:** across repeated runs, write throughput changed by only **±3%** after adding the index, and P95 stayed at 2 ms. At this load the extra cost of updating the index is within run-to-run noise.
- **Trade-off:** a huge gain on reads for a cost on writes that is too small to measure here. For a read-heavy system, this index is clearly worth it.
- **Correlation works:** every journey user found exactly the record it created, with a **0% error rate**.

> Note: write latencies are only a few milliseconds, so JMeter's 1 ms resolution makes small differences look large in percentages. Throughput and repeated runs are more reliable signals.

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
jmeter/person-api-load.jmx           JMeter test plan (Readers, Writers and Journey users thread groups)
jmeter/data/users.csv                test data for the user journey
scripts/summarize.py                 percentiles, before/after tables, performance and error-rate gates
.github/workflows/performance.yml    build, start app, cache JMeter, warm-up, read/write tests before and after the index, journey, compare
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
jmeter -n -t jmeter/person-api-load.jmx -l results/journey.jtl      -Jreaders=0  -Jwriters=0 -Jjourney=5

python3 scripts/summarize.py \
  --run "Before index=results/read-before.jtl,results/write-before.jtl" \
  --run "After index=results/read-after.jtl,results/write-after.jtl"
python3 scripts/summarize.py --title "User journey" --run "Journey=results/journey.jtl"
```

To run again without the index: `DROP INDEX idx_person_email;`

## Related projects

- [api-test-automation-framework](https://github.com/raykurt/api-test-automation-framework) – API tests with Java, REST Assured and Cucumber
- [playwright-typescript-ui-tests](https://github.com/raykurt/playwright-typescript-ui-tests) – UI tests with Playwright and TypeScript
- [cypress-cucumber-ui-tests](https://github.com/raykurt/cypress-cucumber-ui-tests) – UI tests with Cypress, Cucumber and TypeScript
