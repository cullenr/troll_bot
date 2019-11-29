BEGIN;

CREATE SCHEMA troll;

DO $$
BEGIN
    IF NOT EXISTS ( SELECT FROM pg_catalog.pg_roles WHERE rolname = 'troll_admin' ) THEN
        CREATE ROLE troll_admin  WITH LOGIN PASSWORD 'rootroot';
    END IF;
END$$;

\i tables.sql

CREATE OR REPLACE FUNCTION troll_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify(lower(TG_TABLE_SCHEMA || '_' || TG_TABLE_NAME || '_' || TG_OP), 
                      row_to_json(NEW)::text);
    RETURN NULL;
END;
$$;

COMMIT;
