"""Which candidate questions reach the model (retrieval finds passages)? Dev helper for questions.yaml."""
from app.chat.pipeline import prepare_answer
from app.db import connect

CANDIDATES = [
    "Tỷ lệ mới mắc và tỷ lệ hiện mắc khác nhau như thế nào?",
    "Tỷ lệ hiện mắc là gì?",
    "Tỷ lệ mới mắc là gì?",
    "Các chỉ số đo lường bệnh trạng gồm những gì?",
    "Độ nhạy và độ đặc hiệu của test sàng lọc là gì?",
    "Nghiên cứu bệnh chứng là gì?",
]

with connect() as conn:
    for q in CANDIDATES:
        prepared = [v for k, v in prepare_answer(conn, q) if k == "prepared"][0]
        state = prepared.outcome.state if prepared.outcome else "to_model"
        print(f"{state:22} {len(prepared.passages)} | {q} | {[p.competency_code for p in prepared.passages][:3]}")
