# JMeter Performance Lab

![Performance Tests](https://github.com/raykurt/jmeter-performance-lab/actions/workflows/performance.yml/badge.svg)

A small **Spring Boot + PostgreSQL** service with **1,000,000 rows**, used as a target for **Apache JMeter** load tests.
The pipeline finds a real bottleneck, fixes it, and proves the fix with numbers:

1. Load test the API → the email search is slow
2. Check the query plan → PostgreSQL scans the whole table (`Seq Scan`)
3. Add an index on `email` → the plan becomes an `Index Scan`
4. Load test again → compare Average, Median, P90, P95, P99, throughput and error rate
5. A **performance gate** fails the build if P95 goes above the limit

Everything runs in **GitHub Actions** on every push.

## What it shows

- **JMeter test plan** with parameters (`-Jusers`, `-Jduration`, `-Jhost`, `-Jport`), random test data and response assertions
- **Warm-up run** before measuring, so JVM start-up does not distort the results
- **Before/after comparison** of the same scenario, with HTML dashboards for both runs
- **Percentile-based analysis** (P90/P95/P99), not only averages
- **Performance gate in CI**: P95 of each request must stay under 200 ms after the fix
- **Root cause analysis** at the database level with `EXPLAIN ANALYZE`

## Results

Measured in GitHub Actions (10 concurrent users, 5 s ramp-up, 30 s per run). Full JMeter HTML dashboards are in the `jmeter-reports` artifact of each [run](https://github.com/raykurt/jmeter-performance-lab/actions).

| Request | Run | Samples | Avg (ms) | P90 | P95 | P99 | Throughput (req/s) | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Search person by email | Before index | 771 | 356 | 595 | **644** | 763 | 25.6 | 0% |
| Search person by email | After index | 85,822 | 2 | 3 | **3** | 5 | 2,867.5 | 0% |
| Get person by id | Before index | 761 | 5 | 9 | 11 | 15 | 25.6 | 0% |
| Get person by id | After index | 85,816 | 2 | 3 | 3 | 5 | 2,869.9 | 0% |

**Takeaways**

- Email search P95 dropped from **644 ms to 3 ms** (about 200x faster).
- Total throughput grew from **~51 to ~5,700 requests per second** (over 100x).
- The fast `Get person by id` request was also stuck at 25.6 req/s before the fix: each virtual user runs both requests in a loop, so **one slow endpoint limited the capacity of the whole system**.
- The performance gate (P95 < 200 ms after the fix) passed for both requests.

## Query plan

```sql
EXPLAIN ANALYZE
SELECT id, first_name, last_name, email, city, created_at FROM person WHERE email = 'user777777@example.com';
```

- **Before:** `Parallel Seq Scan on person`, every request reads the whole table, and requests queue up under load
- **After** (`CREATE INDEX idx_person_email ON person (email)`): `Index Scan using idx_person_email`, a single lookup

## Project structure

```
src/main/java/com/raykurt/perflab/   Spring Boot app (GET /api/persons?email=..., GET /api/persons/{id})
src/main/resources/schema.sql        creates the table and seeds 1,000,000 rows (no email index on purpose)
sql/add-index.sql                    the fix
jmeter/person-api-load.jmx           JMeter test plan
scripts/summarize.py                 percentiles, before/after table, performance gate
.github/workflows/performance.yml    build, start app, warm-up, before run, add index, after run, compare
docker-compose.yml                   PostgreSQL for local runs
```

## Run locally

```bash
docker compose up -d                       # PostgreSQL
mvn spring-boot:run                        # app on http://localhost:8080 (first start seeds the data)

jmeter -n -t jmeter/person-api-load.jmx -l results/before.jtl -e -o reports/before
psql -h localhost -U perflab -d perflab -f sql/add-index.sql     # password: perflab
jmeter -n -t jmeter/person-api-load.jmx -l results/after.jtl -e -o reports/after

python3 scripts/summarize.py --run "Before index=results/before.jtl" --run "After index=results/after.jtl"
```

To run again without the index: `DROP INDEX idx_person_email;`

## Related projects

- [api-test-automation-framework](https://github.com/raykurt/api-test-automation-framework) – API tests with Java, REST Assured and Cucumber
- [playwright-typescript-ui-tests](https://github.com/raykurt/playwright-typescript-ui-tests) – UI tests with Playwright and TypeScript
- [cypress-cucumber-ui-tests](https://github.com/raykurt/cypress-cucumber-ui-tests) – UI tests with Cypress, Cucumber and TypeScript
