DROP TABLE IF EXISTS users;
CREATE TABLE users (
    snowflake BIGINT PRIMARY KEY NOT NULL,
    username TEXT UNIQUE NOT NULL,
    nickname TEXT,
    picture TEXT,
    passwordhash BYTEA NOT NULL
);
DROP TABLE IF EXISTS tokens;
CREATE TABLE tokens (
    token TEXT UNIQUE PRIMARY KEY NOT NULL,
    snowflake BIGINT NOT NULL,
    session_name TEXT NOT NULL
);
DROP TABLE IF EXISTS ratelimit;
CREATE TABLE ratelimit (
    snowflake BIGINT NOT NULL,
    timecalled INT NOT NULL,
    apiendpoint TEXT NOT NULL
);
DROP TABLE IF EXISTS friends;
DROP TABLE IF EXISTS blocked;


DROP TABLE IF EXISTS servers;
CREATE TABLE servers (
    snowflake BIGINT NOT NULL,
    picture TEXT,
    owner_snowflake BIGINT NOT NULL,
    name TEXT NOT NULL
);
DROP TABLE IF EXISTS server_access;
CREATE TABLE server_access (
    user_snowflake BIGINT NOT NULL,
    server_snowflake BIGINT NOT NULL
);
DROP TABLE IF EXISTS server_channels;
CREATE TABLE server_channels (
    server_snowflake BIGINT NOT NULL,
    channel_snowflake BIGINT NOT NULL
);


DROP TABLE IF EXISTS channels;
CREATE TABLE channels (
    snowflake BIGINT NOT NULL,
    name TEXT NOT NULL,
    picture TEXT
);
DROP TABLE IF EXISTS channel_access;
CREATE TABLE channel_access (
    user_snowflake BIGINT NOT NULL,
    channel_snowflake BIGINT NOT NULL
);


DROP TABLE IF EXISTS messages;
CREATE TABLE messages (
    author_snowflake BIGINT NOT NULL,
    channel_snowflake BIGINT NOT NULL,
    snowflake BIGINT NOT NULL,
    content TEXT NOT NULL
);