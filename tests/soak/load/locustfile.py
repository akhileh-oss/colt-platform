"""Load generator for a real staging soak run (CLAUDE.md §96, Milestone 27's literal "thousands
of mocked leads" Build item) — Milestone 27's own `tests/soak/` suite proves the chaos/
concurrency properties for real against local Postgres/Redis at a few-hundred-row scale
(documented there as a deliberate scale-down for a routine regression suite); this file is the
other half, meant to run against a real, Terraform-provisioned staging environment at the
literal scale the milestone names, which no AWS account exists in this sandbox to provision.

**Not run in this sandbox — `docs/runbooks/staging-soak.md` is the actual procedure.** This
file is the tool that procedure drives, built and ready, not a claim that it has been executed
against real staging.

Usage once a real staging URL exists:

    uv run locust -f tests/soak/load/locustfile.py --host https://staging.colt.example.com \\
        --users 50 --spawn-rate 5 --run-time 30m --headless --csv=soak-results

Every request is read-only against unauthenticated, non-mutating endpoints
(`GET /api/v1/meta`, `GET /`) deliberately: this generates real traffic volume and connection
churn without creating the thousands of real `Company`/`Person`/`Lead` rows a genuine
`DiscoverCompany`/`DiscoverPerson`-driven load test would — seeding that volume of realistic
mocked leads is `docs/runbooks/staging-soak.md`'s own seed-data step, run once before the load
test starts, not something this file repeats on every simulated user's every request.
"""

from __future__ import annotations

from locust import HttpUser, between, task


class ColtUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(3)
    def api_meta(self) -> None:
        self.client.get("/api/v1/meta")

    @task(1)
    def web_root(self) -> None:
        self.client.get("/")
