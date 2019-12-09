
CREATE TABLE troll.users (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR,
    encoding          DOUBLE PRECISION[],
    date_created      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS notify_trigger ON troll.users;
CREATE TRIGGER notify_trigger AFTER INSERT OR UPDATE ON troll.users
    FOR EACH ROW EXECUTE PROCEDURE notify();

GRANT ALL    ON ALL SEQUENCES IN SCHEMA troll  TO troll_admin;
GRANT ALL    ON ALL TABLES    IN SCHEMA troll  TO troll_admin;
GRANT USAGE  ON                  SCHEMA troll  TO troll_admin;
