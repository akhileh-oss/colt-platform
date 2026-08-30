-- A restricted role for the running application, distinct from the `colt` bootstrap role that
-- owns the schema and runs migrations.
--
-- PostgreSQL superusers — which the POSTGRES_USER bootstrap role always is — bypass Row-Level
-- Security unconditionally, regardless of ENABLE/FORCE ROW LEVEL SECURITY on a table (CLAUDE.md
-- §9.7, ADR-0005). If the application connected as that same role, every RLS policy in this
-- repository would be silent dead code: this was caught by testing, not by inspection, so it is
-- worth being explicit about here rather than only in a comment on the policy itself.
--
-- `colt_app` can read and write rows but cannot create, alter, or drop tables — DDL stays with
-- the migration role, which is its own least-privilege boundary (CLAUDE.md §40).
--
-- Local-only development password, deliberately weak and deliberately committed — same pattern
-- as every other credential in this file (CLAUDE.md §6.4, §7.2).
CREATE ROLE colt_app WITH LOGIN PASSWORD 'colt_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;

GRANT CONNECT ON DATABASE colt TO colt_app;
GRANT USAGE ON SCHEMA public TO colt_app;

-- Applies to tables that exist yet; the ALTER DEFAULT PRIVILEGES below covers every table a
-- future migration creates as `colt`, so no migration needs its own GRANT statements.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO colt_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO colt_app;

ALTER DEFAULT PRIVILEGES FOR ROLE colt IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO colt_app;
ALTER DEFAULT PRIVILEGES FOR ROLE colt IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO colt_app;
