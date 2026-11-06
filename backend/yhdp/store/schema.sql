-- Schema v1 (PRAGMA user_version = 1). JSON lives in TEXT columns, read with JSON1.

CREATE TABLE documents (
    doc_id   TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    issuer   TEXT,
    year     INTEGER,
    kind     TEXT NOT NULL,
    citation TEXT NOT NULL            -- section | page
);

CREATE TABLE chunks (
    chunk_id      TEXT PRIMARY KEY,   -- doc_id#anchor#cNN
    doc_id        TEXT NOT NULL REFERENCES documents ON DELETE CASCADE,
    seq           INTEGER NOT NULL,   -- reading order within the document
    content_hash  TEXT NOT NULL,      -- sha1 of the normalized chunk text (tag pinning)
    kind          TEXT NOT NULL,      -- text | table | figure | box | formula
    text          TEXT NOT NULL,
    search_text   TEXT NOT NULL,      -- title + section path + text: what is embedded and indexed
    loc           TEXT NOT NULL,      -- json Loc
    parent_anchor TEXT NOT NULL,
    tokens        INTEGER NOT NULL,
    extra         TEXT NOT NULL DEFAULT '{}'  -- json: figure_path, caption, needs_review, refs
);
CREATE INDEX chunks_doc_seq ON chunks (doc_id, seq);
CREATE INDEX chunks_parent ON chunks (doc_id, parent_anchor);

-- Vectors are keyed by the hash of search_text, so a moved section is re-embedded.
CREATE TABLE chunk_vectors (
    chunk_id    TEXT NOT NULL REFERENCES chunks ON DELETE CASCADE,
    model       TEXT NOT NULL,
    search_hash TEXT NOT NULL,
    vec         BLOB NOT NULL,        -- float32, L2-normalized
    PRIMARY KEY (chunk_id, model)
);

CREATE VIRTUAL TABLE chunks_fts USING fts5 (
    chunk_id UNINDEXED,
    body,
    tokenize = 'unicode61 remove_diacritics 0'  -- Vietnamese: "sốt" and "sót" stay distinct
);

-- No foreign key to chunks: human tags must survive re-ingestion.
CREATE TABLE chunk_tags (
    chunk_id     TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    tags         TEXT NOT NULL,       -- json, design §4.3
    source       TEXT NOT NULL CHECK (source IN ('auto', 'human')),
    reviewer     TEXT,
    ts           TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chunk_id, content_hash, source)
);

CREATE TABLE review_items (
    id       INTEGER PRIMARY KEY,
    kind     TEXT NOT NULL CHECK (kind IN ('tag', 'ocr_page', 'table_rebuild', 'figure_desc',
                                           'dictionary', 'page_map')),
    ref      TEXT NOT NULL,
    payload  TEXT NOT NULL DEFAULT '{}',
    status   TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'skipped')),
    reviewer TEXT,
    ts       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (kind, ref)
);

CREATE TABLE users (
    id       INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    pw_hash  TEXT NOT NULL,
    role     TEXT NOT NULL CHECK (role IN ('reviewer', 'learner'))
);
