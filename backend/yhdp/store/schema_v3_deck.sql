-- Schema v3: adaptive practice (phase 1) — confidence ratings, topic sets made from chat,
-- and the spaced-review deck.

-- sure | unsure | guess, asked before the answer is revealed; null = not asked (exams)
ALTER TABLE mcq_attempts ADD COLUMN confidence TEXT;
-- topic sets created from chat; null = blueprint mock exam
ALTER TABLE mcq_sets ADD COLUMN title TEXT;

-- A card schedules a concept for review, not a question: origin 'mcq' cards are one per
-- learner per source chunk (the missed item's target chunk) and are reviewed with a different
-- item from that chunk when one exists; origin 'chat' cards are front/back notes made in chat.
-- step: -1 relearn (minutes), 0..3 index into the day intervals, 4 = mastered (due null).
CREATE TABLE revision_cards (
    id          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL,
    origin      TEXT NOT NULL CHECK (origin IN ('mcq', 'chat')),
    chunk_id    TEXT,
    item_id     INTEGER REFERENCES mcq_items,
    front       TEXT,
    back        TEXT,                 -- [S#] = sources[#-1]
    sources     TEXT NOT NULL DEFAULT '[]',  -- json [{"chunk_id", "content_hash"}]
    step        INTEGER NOT NULL DEFAULT 0,
    due         TEXT,
    lapses      INTEGER NOT NULL DEFAULT 0,
    reviews     INTEGER NOT NULL DEFAULT 0,
    created     TEXT NOT NULL DEFAULT (datetime('now')),
    last_review TEXT
);
CREATE UNIQUE INDEX revision_cards_chunk ON revision_cards (username, chunk_id)
    WHERE origin = 'mcq';
CREATE INDEX revision_cards_due ON revision_cards (username, due);

CREATE TABLE card_reviews (
    id       INTEGER PRIMARY KEY,
    card_id  INTEGER NOT NULL REFERENCES revision_cards ON DELETE CASCADE,
    rating   TEXT NOT NULL CHECK (rating IN ('again', 'hard', 'good')),
    item_id  INTEGER REFERENCES mcq_items,  -- null = flashcard review
    ts       TEXT NOT NULL DEFAULT (datetime('now'))
);
