-- Extensions required by the Colt application database.
-- Runs once, on first initialisation of the postgres data volume.

-- Semantic representations for research retrieval (CLAUDE.md §3.4, §19.1).
-- PostgreSQL remains the system of record; vectors serve retrieval, never truth.
CREATE EXTENSION IF NOT EXISTS vector;

-- Deterministic UUID generation helpers for database-generated primary keys (§9.2).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
