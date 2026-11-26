"""Chapter anchors transcribed from OCR of start pages of the two pilot sources.

Each profile is tied to the exact source file. These are draft layout anchors, not expert-reviewed
classifications. Page indices start at 1 in the input DOCX.
"""

OUTLINES = {
    "78b02a87b28348ebe09a4a68905553379d851be4afbcbd3d520f4eb4f295412a": {
        1: "Phần đầu tài liệu",
        4: "Mục lục",
        6: "Các chữ viết tắt",
        8: "Chương 1. Các biện pháp chung",
        16: "Chương 2. Các trường hợp ngộ độc cụ thể",
    },
    "51e184938defd0dfad9f02929068f34938ea2a087109aab725bed197f67af449": {
        1: "Phần đầu tài liệu",
        4: "Mục lục",
        14: "Lời nói đầu",
        16: "Giới thiệu",
        18: "Chương 1. Dịch tễ học là gì?",
        34: "Chương 2. Đo lường sức khỏe và bệnh tật",
        58: "Chương 3. Các thiết kế nghiên cứu",
        84: "Chương 4. Các thống kê sinh học cơ bản: Các khái niệm và công cụ",
        106: "Chương 5. Tính nguyên nhân trong dịch tễ học",
        124: "Chương 6. Dịch tễ học và phòng ngừa các bệnh không lây nhiễm",
        144: "Chương 7. Các bệnh truyền nhiễm: giám sát dịch tễ học và phản hồi",
        162: "Chương 8. Dịch tễ học lâm sàng",
        174: "Chương 9. Dịch tễ học môi trường và nghề nghiệp",
        194: "Chương 10. Dịch tễ học, chính sách y tế và lập kế hoạch y tế",
        208: "Chương 11. Các bước đầu tiên trong dịch tễ học thực hành",
        220: "Phụ lục. Trả lời câu hỏi",
    },
}

_NGODOC = "78b02a87b28348ebe09a4a68905553379d851be4afbcbd3d520f4eb4f295412a"
_C1 = "Chương 1. Các biện pháp chung"
_C2 = "Chương 2. Các trường hợp ngộ độc cụ thể"
_G21 = "Phần 2.1. Thuốc tân dược"
_G22 = "Phần 2.2. Các hóa chất bảo vệ thực vật"
_G23 = "Phần 2.3. Các chất độc tự nhiên"
_G24 = "Phần 2.4. Các chất ma túy, lạm dụng"
_G25 = "Phần 2.5. Các chất độc trong môi trường, nghề nghiệp"


def _topic(chapter, group, title, match=None, cont=None):
    return {"chapter": chapter, "group": group, "title": title, "match": match or title, "cont": cont}


# Topic (bài) titles transcribed from the printed table of contents and checked against the title line
# on each topic's first page. Order matters: topics are matched in sequence inside their chapter, so a
# running header or a cross-reference cannot reopen an earlier topic. Draft anchors, review with the source.
TOPICS = {
    _NGODOC: [
        _topic(_C1, None, "CHẨN ĐOÁN VÀ XỬ TRÍ CHUNG VỚI NGỘ ĐỘC CẤP"),
        _topic(_C2, _G21, "NGỘ ĐỘC BARBITURAT"),
        _topic(_C2, _G21, "NGỘ ĐỘC BENZODIAZEPIN"),
        _topic(_C2, _G21, "NGỘ ĐỘC ROTUNDIN"),
        _topic(_C2, _G21, "NGỘ ĐỘC PARACETAMOL"),
        _topic(_C2, _G22, "NGỘ ĐỘC CẤP HÓA CHẤT TRỪ SÂU PHOSPHO HỮU CƠ"),
        _topic(_C2, _G22, "NGỘ ĐỘC NEREISTOXIN"),
        _topic(_C2, _G22, "NGỘ ĐỘC PARAQUAT"),
        _topic(_C2, _G22, "NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT LOẠI MUỐI PHOSPHUA (PHOSPHUA KẼM, PHOSPHUA NHÔM)",
               match="NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT LOẠI MUỐI PHOSPHUA", cont="(PHOSPHUA KẼM, PHOSPHUA NHÔM)"),
        _topic(_C2, _G22, "NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT LOẠI NATRI FLUOROACETAT VÀ FLUOROACETAMID",
               match="NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT", cont="LOẠI NATRI FLUOROACETAT VÀ FLUOROACETAMID"),
        _topic(_C2, _G22, "NGỘ ĐỘC CARBAMAT"),
        _topic(_C2, _G22, "NGỘ ĐỘC CLO HỮU CƠ"),
        _topic(_C2, _G22, "NGỘ ĐỘC CẤP STRYCHNIN"),
        _topic(_C2, _G22, "NGỘ ĐỘC CẤP CÁC CHẤT KHÁNG VITAMIN K"),
        _topic(_C2, _G23, "RẮN HỔ MANG CẮN"),
        _topic(_C2, _G23, "RẮN CẠP NIA CẮN"),
        _topic(_C2, _G23, "RẮN HỔ MÈO CẮN"),
        _topic(_C2, _G23, "RẮN LỤC CẮN"),
        _topic(_C2, _G23, "RẮN CHÀM QUẠP CẮN"),
        _topic(_C2, _G23, "ONG ĐỐT"),
        _topic(_C2, _G23, "NGỘ ĐỘC MẬT CÁ TRẮM, CÁ TRÔI"),
        _topic(_C2, _G23, "NGỘ ĐỘC NẤM ĐỘC"),
        _topic(_C2, _G23, "NGỘ ĐỘC TETRODOTOXIN"),
        _topic(_C2, _G23, "NGỘ ĐỘC LÁ NGÓN"),
        _topic(_C2, _G23, "DỊ ỨNG DỨA"),
        _topic(_C2, _G23, "NGỘ ĐỘC NỌC CÓC"),
        _topic(_C2, _G23, "NGỘ ĐỘC ACONITIN"),
        _topic(_C2, _G24, "NGỘ ĐỘC RƯỢU ETHANOL"),
        _topic(_C2, _G24, "NGỘ ĐỘC RƯỢU METHANOL"),
        _topic(_C2, _G24, "NGỘ ĐỘC CẤP AMPHETAMIN"),
        _topic(_C2, _G24, "NGỘ ĐỘC MA TÚY NHÓM OPI"),
        _topic(_C2, _G25, "NGỘ ĐỘC CHÌ"),
        _topic(_C2, _G25, "NGỘ ĐỘC KHÍ CARBON MONOXIDE (CO)"),
        _topic(_C2, _G25, "NGỘ ĐỘC CYANUA"),
        _topic(_C2, _G25, "NGỘ ĐỘC CẤP CÁC CHẤT GÂY METHEMOGLOBIN"),
    ],
}
