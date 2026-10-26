"""Every number the sample cohort is drawn from. Nothing here is a product setting: these shape
sample data only, and changing one changes what the next cohort looks like."""
import random


def rng_for(seed: int, *parts) -> random.Random:
    """A generator of its own for one concern (one learner, one question), so what is drawn for it
    does not depend on what was drawn for the others."""
    return random.Random(":".join(map(str, (seed, *parts))))


# ---- the sample bank -----------------------------------------------------------------------------

SAMPLE_PREFIX = "SMP-"
SAMPLE_FORM_ID = "SMP-MOCK-01"
SAMPLE_FORM_TITLE = "Đề thi thử mẫu 1"
SAMPLE_COMMENT = "Dữ liệu mẫu"
SAMPLE_DOCUMENT_ID = "SMP-DOC"
SAMPLE_DOCUMENT_TITLE = "Tài liệu mẫu"
SECONDS_PER_QUESTION = 72

APPROVED_PER_ISSUE = 11
THIN_ISSUES = (5, 16, 19, 29, 51, 54)       # core issues left under 10 approved items
APPROVED_THIN = 6

# The sample mock form: questions per exam competency 1–4, by core-issue group. Rows sum to
# 7/8/3/8/1/10/2/1 and columns to 8/16/14/2, the split in docs/data-model.md §3.1.
FORM_SPLIT = {1: (2, 3, 2, 0), 2: (1, 3, 4, 0), 3: (1, 1, 1, 0), 4: (1, 4, 3, 0),
              5: (0, 1, 0, 0), 6: (2, 4, 3, 1), 7: (1, 0, 1, 0), 8: (0, 0, 0, 1)}

DIFFICULTY_WEIGHTS = {"de": 0.3, "trung_binh": 0.5, "kho": 0.2}
R1_DAYS = (1.0, 7.0)                        # days an item waits in round 1, uniform
R2_DAYS = (4.0, 14.0)                       # and in round 2: its median is over the 7-day target

# How many sample questions end in each state with a history dated inside the cohort's weeks.
PIPELINE = {"approved": 60, "in_review_r1": 60, "in_review_r2": 60,
            "revise_r1": 22, "revise_r2": 8, "reject_r1": 34, "reject_r2": 6, "draft": 200}

# ---- the people ----------------------------------------------------------------------------------

# (code, name, region, weight among the large schools, activation rate, week it joins)
SCHOOLS = [("CSDT-A", "CSĐT A", "Miền Bắc", 0.31, 0.87, 0), ("CSDT-B", "CSĐT B", "Miền Nam", 0.27, 0.81, 0),
           ("CSDT-C", "CSĐT C", "Miền Bắc", 0.20, 0.78, 0), ("CSDT-D", "CSĐT D", "Miền Trung", 0.15, 0.74, 4),
           ("CSDT-E", "CSĐT E", "Miền Nam", 0.07, 0.41, 4)]
SMALL_SCHOOL = ("CSDT-F", "CSĐT F", "Tây Nguyên", 8, 0.80, 2)     # 8 learners: under the suppression minimum
STUDENT_SHARE = 0.70
RESEARCH_CONSENT = 0.64
WITHDRAW_SHARE, DELETE_SHARE = 0.017, 0.010      # of learners; at least one each
ACTIVATION_DELAY_DAYS = 10   # mean days between a school joining and one of its learners activating

# ---- one learner's history -----------------------------------------------------------------------

ABILITY_SD = 1.0             # hidden ability, on the Elo scale
LEARN_RATE = 0.0015          # ability gained per item answered: about 4 more of 40 correct after 300 items
B_NOISE_SD = 0.4             # an item's hidden difficulty around its label
DAYS_PER_WEEK = (1.5, 5.5)   # a learner's study days per week, uniform
WEEKLY_DROPOUT = 0.06        # chance per week of stopping for good
VISIT_HOURS = (7, 22)        # local time a study day starts

RECALL = (0.70, 0.95)        # chance of recalling a card, from the least to the most able
CARD_MS, ITEM_MS = (8_000, 40_000), (30_000, 110_000)
PRACTICE_STEP, UNIT_STEP = 0.85, 0.60     # chance of doing that step on a study day
UNIT_ITEMS_PER_DAY = 8
FIRST_MOCK_WITHIN_DAYS = 5
MOCK_EVERY_DAYS = (18, 28)
MOCK_PACE = (0.60, 0.95)     # share of the time limit used
BLANK_RATE = 0.02

# ---- log records ---------------------------------------------------------------------------------

CHAT_PER_VISIT = 0.35
CHAT_STATES = {"answered": 0.962, "insufficient_evidence": 0.031, "declined": 0.004, "needs_clarification": 0.003}
CLAIMS = (2, 6)
ANSWER_LOSES_A_CLAIM = 0.02
LATENCY_MS = (6_500, 0.4)    # median and sigma of a log-normal
REPORT_PER_VISIT = 0.01      # error reports per visit; at least 3
REPORT_RESOLVED = 0.85
REPORT_REASONS = ("wrong_content", "wrong_citation", "broken_item", "inappropriate", "other")
