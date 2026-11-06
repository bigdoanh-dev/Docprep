"""Tutor moves for Hỏi đáp: what the learner asks the tutor to do with the sources, beyond looking
something up. Each move sets how sources are gathered (yhdp/api/chat.py) and what the answer must
do with them.

  giai_thich  explain (the default): the core point, why, how it applies at primary care, a pitfall
  so_sanh     compare and contrast: sources for each item, a table, and how to tell them apart
  vi_du       worked clinical example: an illustrative case reasoned step by step, facts cited
  kiem_tra    quiz me: one open question answerable from the sources, without its answer
  cham        grade the learner's answer to that question against the same sources
  tom_tat     summarise to remember: key points, the numbers, a mnemonic marked as made up

The client names the move (a chip under an answer, or the reply to a kiem_tra question); otherwise
it is read from the question's wording.
"""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from yhdp.llm import LLMError, Ollama
from yhdp.retrieve import Hit, Retriever

Mode = Literal["auto", "giai_thich", "so_sanh", "vi_du", "kiem_tra", "cham", "tom_tat"]

# Moves about what was just discussed: their sources are the previous answer's, when there are any.
FOLLOW_ON = ("vi_du", "kiem_tra", "tom_tat", "cham")

# Wording that asks for a move, matched without diacritics; the first match wins.
CUES: list[tuple[str, re.Pattern]] = [
    ("kiem_tra", re.compile(r"\b(?<!cau )(kiem tra|hoi) (toi|minh|em)\b|\btu kiem tra\b")),
    ("so_sanh", re.compile(r"\b(so sanh|phan biet|khac nhau|giong nhau|khac gi|de nham)\b")),
    ("vi_du", re.compile(r"\b(vi du|ca lam sang|ca benh|tinh huong)\b")),
    ("tom_tat", re.compile(r"\b(tom tat|tom luoc|ghi nho|meo nho|y chinh)\b")),
]

NOTES = {
    "giai_thich": "Cách trả lời (gia sư): mở đầu bằng ý chính trong 1–2 câu; giải thích vì sao "
                  "(cơ chế, lý do) khi nguồn có nêu; cách áp dụng tại tuyến y tế cơ sở nếu nguồn "
                  "có; nếu có, chỉ ra một điểm người học hay nhầm. Không kéo dài.",
    "so_sanh": "Cách trả lời (so sánh – phân biệt): 1) Bảng so sánh: mỗi cột là một đối tượng, "
               "mỗi hàng là một tiêu chí; ô nào nguồn không nêu thì ghi 'không nêu'. 2) Điểm giống "
               "nhau chính. 3) Điểm khác biệt then chốt giúp phân biệt khi làm bài thi. 4) Một mẹo "
               "phân biệt nhanh. Mọi ý có nội dung phải có trích dẫn.",
    "vi_du": "Cách trả lời (ca lâm sàng minh họa): 1) Một ca ngắn tại trạm y tế xã hoặc tuyến cơ "
             "sở, người bệnh hư cấu, mở đầu bằng 'Ca minh họa:'; dấu hiệu, ngưỡng số, liều dùng "
             "đúng như trong nguồn. 2) Phân tích từng bước: dữ kiện → nhận định → xử trí, mỗi bước "
             "có trích dẫn. 3) Kết thúc bằng 'Điểm rút ra' 1–2 câu. Không thêm dữ kiện y khoa "
             "hay nhận xét kiểu 'trong thực tế…' ngoài nguồn.",
    "kiem_tra": "Cách trả lời (kiểm tra kiến thức): đặt ĐÚNG MỘT câu hỏi tự luận ngắn (một ý "
                "hỏi, không chia 1), 2)) để người học tự trả lời, ở mức áp dụng hoặc phân tích "
                "(ưu tiên một tình huống 2–3 câu), trả lời được hoàn toàn từ NGUỒN. Tình huống "
                "không được nêu sẵn dữ kiện là đáp án. KHÔNG nêu đáp án, gợi ý đáp án hay trích "
                "dẫn. Chỉ viết câu hỏi, mở đầu bằng 'Câu hỏi:'.",
    "cham": "Tin nhắn trên là câu trả lời của người học cho câu hỏi kiểm tra gần nhất của gia sư. "
            "Chấm theo NGUỒN, giọng khích lệ và không phán xét: 1) Ý đúng. 2) Ý còn thiếu hoặc "
            "chưa chính xác (nếu có). 3) Đáp án đầy đủ, có trích dẫn. 4) Một mẹo ghi nhớ ngắn. Nếu "
            "người học nói chưa biết, bỏ 1–2 và đưa đáp án kèm giải thích. Nếu tin nhắn là một câu "
            "hỏi mới chứ không phải câu trả lời, hãy trả lời câu hỏi đó.",
    "tom_tat": "Cách trả lời (tóm tắt để ôn): 1) Tối đa 7 ý chính, mỗi ý một dòng, có trích dẫn. "
               "2) Bảng các con số, ngưỡng, liều quan trọng (nếu nguồn có). 3) Một 'Mẹo nhớ (tự "
               "đặt)' ngắn, ghi rõ đây là mẹo chứ không phải nội dung tài liệu.",
}

# A little variety where a fresh case or question each time is the point.
TEMPERATURE = {"vi_du": 0.4, "kiem_tra": 0.5}


def unaccent(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return "".join(c for c in text if not unicodedata.combining(c))


def resolve_mode(mode: Mode, question: str) -> str:
    if mode != "auto":
        return mode
    text = unaccent(question)
    return next((m for m, cue in CUES if cue.search(text)), "giai_thich")


def instruct(mode: str, question: str) -> str:
    """The question as the model reads it: the learner's words, then what the move asks for."""
    if mode == "cham":
        return f"Câu trả lời của người học: {question}\n\n({NOTES['cham']})"
    return f"{question}\n\n({NOTES[mode]})"


class Comparison(BaseModel):
    doi_tuong: list[str] = Field(max_length=4)
    tieu_chi: list[str] = Field(max_length=6)


COMPARE_PLAN = """Người học muốn so sánh hoặc phân biệt. Xác định 2–4 đối tượng cần so sánh (bệnh,
thể bệnh, thuốc, phác đồ, phân độ, xét nghiệm…) và 3–6 tiêu chí so sánh phù hợp với kỳ thi bác sĩ
y học dự phòng. Nếu câu hỏi chỉ nêu một đối tượng (VD "so sánh với bệnh dễ nhầm"), thêm đối tượng
dễ nhầm nhất với nó. Dùng hội thoại trước để hiểu "nội dung trên". Viết tên đối tượng đầy đủ bằng
tiếng Việt có dấu.

HỘI THOẠI TRƯỚC:
{earlier}

CÂU HỎI: {question}"""

COMPARE_SOURCES = 12


def plan_comparison(llm: Ollama, retriever: Retriever, question: str,
                    earlier: str) -> tuple[list[Hit], list[str], list[str]] | None:
    """(sources, items, criteria): the passages on each item for the criteria, grouped by item;
    None when the model names fewer than two items or fails (the caller searches as usual)."""
    try:
        plan = llm.chat([{"role": "user", "content": COMPARE_PLAN.format(
            earlier=earlier or "(không có)", question=question)}],
            schema=Comparison, temperature=0.0, retries=1)
    except LLMError:
        return None
    items = list(dict.fromkeys(x.strip() for x in plan.doi_tuong if x.strip()))
    criteria = [x.strip() for x in plan.tieu_chi if x.strip()]
    if len(items) < 2:
        return None
    per = max(2, COMPARE_SOURCES // len(items))
    hits, seen = [], set()
    for item in items:
        for h in retriever.search(f"{item} {' '.join(criteria)}".strip(), k=per):
            if h.chunk_id not in seen:
                seen.add(h.chunk_id)
                hits.append(h)
    return hits, items, criteria
