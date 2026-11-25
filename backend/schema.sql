CREATE TABLE IF NOT EXISTS tasks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title varchar(200) NOT NULL CHECK (length(btrim(title)) > 0),
    description varchar(2000) NOT NULL DEFAULT '',
    completed boolean NOT NULL DEFAULT false
);
