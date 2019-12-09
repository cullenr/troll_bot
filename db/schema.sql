BEGIN;

CREATE SCHEMA troll;

DO $$
BEGIN
    IF NOT EXISTS ( SELECT FROM pg_catalog.pg_roles WHERE rolname = 'troll_admin' ) THEN
        CREATE ROLE troll_admin  WITH LOGIN PASSWORD 'rootroot';
    END IF;
END$$;

CREATE OR REPLACE FUNCTION notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify(
            lower(TG_TABLE_SCHEMA || '_' || TG_TABLE_NAME || '_' || TG_OP), 
            NEW.id::text);
    RETURN NULL;
END;
$$;

\i tables.sql


COMMIT;
