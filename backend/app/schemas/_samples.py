"""Sample values shared by the contract examples.

Every medical fact here comes from the seed content in backend/seed/content; nothing new is stated.
"""

DT_CITATION = {
    "n": 1, "passage_id": "dt-p01", "document": "Dịch tễ học cơ bản", "chapter": "Chương 2. Đo lường bệnh trạng",
    "section": "2.1 Tỷ lệ hiện mắc", "page": 58, "article": None,
}

# Seed question q-dt-01.
Q1_ID = "q-dt-01"
Q1_STEM = "Một xã có 2.000 dân; ngày 1/1 có 50 người đang mắc lao. Tỷ lệ hiện mắc là?"
Q1_OPTIONS = [
    {"key": "a", "text": "2,5%"},
    {"key": "b", "text": "5%"},
    {"key": "c", "text": "0,25%"},
    {"key": "d", "text": "25%"},
]
Q1_CORRECT = "a"
Q1_RATIONALES = {
    "a": "50 ÷ 2.000 = 0,025 = 2,5%.",
    "b": "5% là kết quả của 50 ÷ 1.000; mẫu số phải là toàn bộ 2.000 dân của xã.",
    "c": "Đặt sai dấu thập phân: 50 ÷ 2.000 = 0,025, tức 2,5% chứ không phải 0,25%.",
    "d": "25% là kết quả của 50 ÷ 200; mẫu số phải là 2.000 dân.",
}
Q1_EXPLANATION = ("50 ÷ 2.000 = 2,5%. Tử số là mọi người đang mắc vào ngày 1/1; mẫu số là toàn bộ dân số xã "
                  "tại thời điểm đó.")
Q1_TOPIC = "Đo lường tần suất bệnh"

REMEDIATION = {
    "title": "Ví dụ · Tính từng bước",
    "body": "Một xã có 2.000 dân; ngày 1/1 có 50 người đang mắc lao.\n\n"
            "1. Tử số: 50 người đang mắc.\n2. Mẫu số: toàn bộ 2.000 dân của xã.\n3. 50 ÷ 2.000 = 0,025 = 2,5%.",
    "citations": [DT_CITATION],
    "reason": "Đã thêm 1 ví dụ tính từng bước vì bạn chọn 5%.",
}

# Seed questions q-dt-01 to q-dt-06: (id, stem, option texts a–d).
PRACTICE_QUESTIONS = [
    (Q1_ID, Q1_STEM, ["2,5%", "5%", "0,25%", "25%"]),
    ("q-dt-02",
     "Chỉ số nào chỉ đếm các ca bệnh mới xuất hiện trong một khoảng thời gian, trên quần thể có nguy cơ?",
     ["Tỷ lệ hiện mắc", "Tỷ lệ mới mắc", "Tỷ lệ tử vong trên số mắc", "Nguy cơ tương đối"]),
    ("q-dt-03",
     "Một bệnh mạn tính có tỷ lệ mới mắc không đổi. Nhờ thuốc mới, người bệnh sống lâu hơn nhưng không khỏi bệnh. "
     "Tỷ lệ hiện mắc sẽ thay đổi thế nào?",
     ["Tăng", "Giảm", "Không đổi", "Không xác định được vì hiện mắc không phụ thuộc thời gian mắc bệnh"]),
    ("q-dt-04",
     "Một nghiên cứu thuần tập về tiêm vắc xin và mắc bệnh cho RR = 0,5. Diễn giải nào đúng?",
     ["Người được tiêm có nguy cơ mắc bệnh bằng một nửa người không tiêm",
      "Người được tiêm có nguy cơ mắc bệnh cao gấp 2 lần", "Tiêm vắc xin không liên quan đến mắc bệnh",
      "50% người được tiêm sẽ mắc bệnh"]),
    ("q-dt-05",
     "Nghiên cứu một bệnh hiếm: chọn người bệnh và người không bệnh, rồi hỏi về phơi nhiễm trong quá khứ. "
     "Số đo kết hợp phù hợp là?",
     ["Nguy cơ tương đối tính trực tiếp từ tỷ lệ mới mắc", "Tỷ suất chênh (OR)", "Tỷ lệ hiện mắc",
      "Tỷ lệ tấn công"]),
    ("q-dt-06",
     "Một test sàng lọc được thử trên 200 người có bệnh và cho kết quả dương tính ở 180 người. "
     "Độ nhạy của test là?",
     ["90%", "10%", "80%", "Không tính được vì thiếu số người không có bệnh"]),
]


def options(texts: list[str]) -> list[dict]:
    return [{"key": key, "text": text} for key, text in zip("abcd", texts)]


# Học phần = the eight blueprint groups: (id, official name, short display name).
MODULES = [
    ("g1", "Vấn đề sức khỏe quần thể cần can thiệp ở cấp ban đầu để ngăn ngừa tiến triển",
     "Sức khỏe quần thể và dự phòng"),
    ("g2", "Vấn đề sức khỏe cần cấp cứu, sơ cấp cứu ở cấp ban đầu", "Cấp cứu và sơ cấp cứu"),
    ("g3", "Vấn đề dinh dưỡng, an toàn thực phẩm cần can thiệp ở cấp ban đầu", "Dinh dưỡng và an toàn thực phẩm"),
    ("g4", "Vấn đề bệnh lý truyền nhiễm cần chẩn đoán, xử trí ở cấp ban đầu", "Bệnh truyền nhiễm"),
    ("g5", "Vấn đề sức khỏe nghề nghiệp cần phát hiện và xử trí ở cấp ban đầu", "Sức khỏe nghề nghiệp"),
    ("g6", "Vấn đề sức khỏe cộng đồng cần chẩn đoán và xử trí theo tiếp cận y học gia đình",
     "Sức khỏe cộng đồng và y học gia đình"),
    ("g7", "Vấn đề sức khỏe tâm thần và hành vi cần phát hiện và can thiệp ở cấp ban đầu",
     "Sức khỏe tâm thần và hành vi"),
    ("g8", "Giao tiếp và Cộng tác", "Giao tiếp và cộng tác"),
]
# Number of core issues in each group.
GROUP_SIZES = [5, 11, 3, 8, 2, 19, 3, 3]
