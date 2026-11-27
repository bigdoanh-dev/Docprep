"""Internal extensions of the QĐ 51/QĐ-HĐYKQG issue catalogue.

The 54 official issues do not cover every part of the source corpus. Content with no matching issue could
only abstain or be forced into an unrelated issue, and a chunk without an issue never reaches Chat.
Extensions agreed with the lead:

- 27/11/2026 `noi-bo-dich-te-thong-ke-v1`: background epidemiology and biostatistics (new đề mục 9, issues 55–58).
- 27/11/2026 `noi-bo-benh-truyen-nhiem-bo-sung-v1`: infectious diseases in the BYT guideline with no matching
  issue (issues 59–60 under the official đề mục 4).

These entries are NOT part of QĐ 51. They carry `internal: True` so reports and exam blueprints can exclude
them. Extending a snapshot creates a new taxonomy version; labels made with an earlier version keep it.
"""
import copy

EXTENSIONS = {
    "noi-bo-dich-te-thong-ke-v1": {
        "de_muc": {"id": 9, "name": "Kiến thức nền dịch tễ học và thống kê y sinh (bổ sung nội bộ, không thuộc QĐ 51)"},
        "issues": [
            {"id": 55, "name": "Đo lường sức khỏe và bệnh tật trong quần thể",
             "description": "Tỷ lệ hiện mắc, tỷ lệ mới mắc, tỷ suất tử vong, tỷ suất chuẩn hóa theo tuổi, chỉ số gánh nặng "
                            "bệnh tật (DALY…), nguồn số liệu và cách so sánh sự xuất hiện bệnh giữa các quần thể."},
            {"id": 56, "name": "Thiết kế nghiên cứu dịch tễ học và sai số",
             "description": "Nghiên cứu mô tả, cắt ngang, sinh thái, bệnh–chứng, thuần tập, thử nghiệm can thiệp; đo lường "
                            "kết hợp (nguy cơ tương đối, tỷ số chênh); sai số ngẫu nhiên, sai số hệ thống, yếu tố nhiễu, đạo đức nghiên cứu."},
            {"id": 57, "name": "Thống kê y sinh cơ bản",
             "description": "Mô tả số liệu, phân phối, ước lượng, khoảng tin cậy, kiểm định giả thuyết, giá trị p, cỡ mẫu, "
                            "tương quan và hồi quy, cách diễn giải kết quả thống kê."},
            {"id": 58, "name": "Suy luận nhân quả, sàng tuyển và dịch tễ học lâm sàng",
             "description": "Tiêu chuẩn đánh giá quan hệ nhân quả, bằng chứng khoa học; sàng tuyển (độ nhạy, độ đặc hiệu, giá trị "
                            "dự đoán); định nghĩa bình thường–bất thường, y học dựa trên bằng chứng; dịch tễ học trong chính sách và lập kế hoạch y tế."},
        ],
    },
    "noi-bo-benh-truyen-nhiem-bo-sung-v1": {
        "de_muc_id": 4,  # official đề mục: Vấn đề bệnh lý truyền nhiễm cần chẩn đoán, xử trí ở cấp ban đầu
        "issues": [
            {"id": 59, "name": "Uốn ván (bổ sung nội bộ)",
             "description": "Nhận biết uốn ván (cứng hàm, co cứng, co giật), xử lý vết thương, kháng sinh, huyết thanh và "
                            "vắc xin, kiểm soát co giật, hồi sức và chuyển tuyến."},
            {"id": 60, "name": "Nhiễm trùng da và mô mềm nặng (bổ sung nội bộ)",
             "description": "Chốc, viêm mô bào, viêm cân mạc hoại tử, hoại thư Fournier: nhận biết dấu hiệu nặng, kháng sinh, "
                            "xử trí ngoại khoa và hồi sức, chuyển tuyến."},
        ],
    },
}
# Backward-compatible names for the first extension.
EXTENSION_ID = "noi-bo-dich-te-thong-ke-v1"
DE_MUC = EXTENSIONS[EXTENSION_ID]["de_muc"]
ISSUES = EXTENSIONS[EXTENSION_ID]["issues"]


def extend(payload, extension_id=EXTENSION_ID):
    """A copy of a taxonomy with one internal extension appended. Refuses to apply twice or clash on ids."""
    ext = EXTENSIONS[extension_id]
    out = copy.deepcopy(payload)
    if extension_id in out.get("extensions", []):
        raise ValueError("Taxonomy already carries this extension")
    if {i["id"] for i in ext["issues"]} & {v["id"] for v in out["van_de"]}:
        raise ValueError("Extension ids clash with the taxonomy")
    if "de_muc" in ext:
        if ext["de_muc"]["id"] in {d["id"] for d in out["de_muc"]}:
            raise ValueError("Extension đề mục clashes with the taxonomy")
        out["de_muc"].append(dict(ext["de_muc"]))
        de_muc_id = ext["de_muc"]["id"]
    else:
        de_muc_id = ext["de_muc_id"]
        if de_muc_id not in {d["id"] for d in out["de_muc"]}:
            raise ValueError("Unknown đề mục for extension")
    out["van_de"] += [{**issue, "de_muc": de_muc_id, "approved": False, "internal": True} for issue in ext["issues"]]
    out["extensions"] = [*out.get("extensions", []), extension_id]
    return out
