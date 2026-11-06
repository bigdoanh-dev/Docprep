-- Schema v2: MCQ item bank, practice attempts and mock-exam sets (design §7).

-- validated: passed the automatic checks, usable, not yet seen by a reviewer
-- approved / rejected: reviewer decision; flagged: a learner reported a problem
-- discarded: failed generation checks (kept for prompt tuning, never shown)
CREATE TABLE mcq_items (
    id           INTEGER PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'validated'
                 CHECK (status IN ('validated', 'approved', 'rejected', 'flagged', 'discarded')),
    van_de       INTEGER NOT NULL,
    de_muc       INTEGER NOT NULL,
    mien         TEXT NOT NULL,
    bloom        TEXT NOT NULL,
    stem         TEXT NOT NULL,       -- clinical vignette
    lead_in      TEXT NOT NULL,
    options      TEXT NOT NULL,       -- json {"A": …, "B": …, "C": …, "D": …}
    answer       TEXT NOT NULL CHECK (answer IN ('A', 'B', 'C', 'D')),
    explanations TEXT NOT NULL,       -- json {"A": {correct, why, mistake?}, …}; [S#] = sources[#-1]
    sources      TEXT NOT NULL,       -- json [{"chunk_id", "content_hash"}]
    validation   TEXT NOT NULL DEFAULT '{}',
    model        TEXT NOT NULL,
    reviewer     TEXT,
    review_note  TEXT,
    created      TEXT NOT NULL DEFAULT (datetime('now')),
    updated      TEXT
);
CREATE INDEX mcq_items_target ON mcq_items (status, de_muc, van_de);

CREATE TABLE mcq_flags (
    id       INTEGER PRIMARY KEY,
    item_id  INTEGER NOT NULL REFERENCES mcq_items,
    username TEXT NOT NULL,
    reason   TEXT NOT NULL,
    ts       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE mcq_sets (
    id         INTEGER PRIMARY KEY,
    username   TEXT NOT NULL,
    size       INTEGER NOT NULL,
    minutes    INTEGER,               -- null = untimed
    items      TEXT NOT NULL,         -- json [item_id, …] in presentation order
    allocation TEXT NOT NULL,         -- json {de_muc: n}
    notes      TEXT NOT NULL DEFAULT '[]',
    started    TEXT NOT NULL DEFAULT (datetime('now')),
    submitted  TEXT,
    report     TEXT
);

CREATE TABLE mcq_attempts (
    id       INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    item_id  INTEGER NOT NULL REFERENCES mcq_items,
    set_id   INTEGER REFERENCES mcq_sets,
    chosen   TEXT,                    -- null = left blank
    correct  INTEGER NOT NULL,
    seconds  REAL,
    mode     TEXT NOT NULL CHECK (mode IN ('practice', 'exam')),
    ts       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX mcq_attempts_user ON mcq_attempts (username, item_id);
