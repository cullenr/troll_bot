
CREATE TABLE troll.users (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR,
    encoding         DOUBLE PRECISION[],
    date_created      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

GRANT ALL    ON ALL SEQUENCES IN SCHEMA troll  TO troll_admin;
GRANT ALL    ON ALL TABLES    IN SCHEMA troll  TO troll_admin;
GRANT USAGE  ON                  SCHEMA troll  TO troll_admin;
