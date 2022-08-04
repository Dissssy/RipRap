DROP TABLE IF EXISTS users;
CREATE TABLE users (
    snowflake TEXT PRIMARY KEY NOT NULL,
    username TEXT UNIQUE NOT NULL,
    nickname TEXT,
    pfp TEXT,
    passwordhash BYTEA NOT NULL,
    servers BYTEA DEFAULT '\x789CABAE0500017500F9',
    friends BYTEA DEFAULT '\x789CABAE0500017500F9',
    blocked BYTEA DEFAULT '\x789CABAE0500017500F9'
);
DROP TABLE IF EXISTS tokens;
CREATE TABLE tokens (
    token TEXT UNIQUE PRIMARY KEY NOT NULL,
    snowflake TEXT NOT NULL,
    session_name TEXT NOT NULL
);
DROP TABLE IF EXISTS ratelimit;
CREATE TABLE ratelimit (
    snowflake TEXT NOT NULL,
    timecalled INT NOT NULL,
    apiendpoint TEXT NOT NULL
)