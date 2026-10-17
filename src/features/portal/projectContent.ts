import type { ProjectPageContent } from "./ProjectPage";
const action = { to: "/dang-nhap", label: "Vào không gian học tập" };
export const projectPages: Record<string, ProjectPageContent> = {
  about: {
    title: "Nền tảng số AI hỗ trợ ôn thi Bác sĩ Y học dự phòng (BSYHDP)",
    intro:
      "DocPrep YHDP là nền tảng số tích hợp Trí tuệ nhân tạo (AI) được nghiên cứu và phát triển bởi AIRC - Trung tâm nghiên cứu tiên tiến quốc tế về trí tuệ nhân tạo ứng dụng, phối hợp chuyên môn cùng Viện Đào tạo Y học dự phòng và Y tế công cộng, Trường Đại học Y Hà Nội. Đề tài hướng tới chuẩn hóa hoạt động tự ôn luyện, đánh giá năng lực và chuẩn bị cho kỳ kiểm tra đánh giá năng lực hành nghề quốc gia.",
    photo: {
      src: "/images/medical/vietnam-medical-training.webp",
      alt: "Sinh viên y khoa và bác sĩ nội trú thảo luận ca lâm sàng qua hồ sơ bệnh án và phim chụp CT",
      caption:
        "Môi trường học tập lâm sàng: kết nối chặt chẽ giữa lý thuyết y văn và phân tích tình huống thực tế.",
    },
    sections: [
      {
        id: "boi-canh",
        title: "Bối cảnh nghiên cứu & Nhu cầu cấp thiết",
        paragraphs: [
          "Triển khai Luật Khám bệnh, chữa bệnh số 15/2023/QH15 và định hướng của Hội đồng Y khoa Quốc gia, việc kiểm tra đánh giá năng lực hành nghề là yêu cầu bắt buộc để cấp giấy phép hành nghề. Bác sĩ Y học dự phòng (BSYHDP) giữ vai trò then chốt trong y tế cơ sở và y tế công cộng, đòi hỏi phải nắm vững 8 nhóm chuẩn năng lực từ giám sát dịch tễ, kiểm soát ổ dịch, dinh dưỡng cộng đồng, bệnh nghề nghiệp đến xử trí cấp cứu ban đầu.",
          "Nền tảng DocPrep YHDP ra đời nhằm giải quyết bài toán: kết nối học liệu chuẩn hóa, ngân hàng câu hỏi thẩm định 2 vòng, Trợ lý giải đáp có trích dẫn nguồn y văn chính thống và công cụ thi thử trắc nghiệm đánh giá toàn diện năng lực.",
        ],
      },
      {
        id: "chu-tri",
        title: "Đơn vị nghiên cứu & Cơ quan chủ trì",
        paragraphs: [
          "AIRC phụ trách phát triển công cụ học tập: tìm tài liệu liên quan, hỗ trợ giải thích bài học và tổng hợp kết quả luyện tập. Người học không cần kiến thức về trí tuệ nhân tạo để sử dụng.",
          "Đơn vị chủ trì nhiệm vụ chuyên môn: Viện Đào tạo Y học dự phòng và Y tế công cộng, Trường Đại học Y Hà Nội, phụ trách xây dựng khung 54 vấn đề cốt lõi, biên soạn học liệu và tổ chức Hội đồng Chuyên gia Y khoa thẩm định 2 vòng độc lập.",
        ],
      },
      {
        id: "muc-tieu",
        title: "Bốn mục tiêu nghiên cứu của đề tài",
        items: [
          "Khảo sát năng lực số và mức độ sẵn sàng sử dụng nền tảng của sinh viên năm cuối và bác sĩ YHDP mới tốt nghiệp.",
          "Xây dựng kho nội dung ôn luyện chuẩn hóa gắn với 54 vấn đề cốt lõi và phát triển nền tảng số tích hợp Trợ lý đối chiếu y văn có kiểm soát.",
          "Thí điểm, đánh giá hiệu quả can thiệp đối với kết quả học tập và mức độ sẵn sàng cho kỳ thi quốc gia.",
          "Đánh giá mức độ dễ sử dụng, khả năng áp dụng tại cơ sở đào tạo và chi phí duy trì lâu dài.",
        ],
      },
      {
        id: "pham-vi",
        title: "Phạm vi học liệu & Chuẩn năng lực Bộ Y tế",
        paragraphs: [
          "Trọng tâm của đề tài là Bác sĩ Y học dự phòng, bám sát 8 nhóm chuẩn năng lực cơ bản theo Quyết định của Bộ Y tế và 54 vấn đề sức khỏe ưu tiên cốt lõi nêu trong thuyết minh.",
          "Bản giao diện hiện tại cho phép trải nghiệm toàn bộ các luồng học tập, hỏi đáp AI, ôn thẻ và thi thử với dữ liệu minh họa bám sát tài liệu dự án.",
        ],
      },
    ],
    action,
  },
  research: {
    title: "Nghiên cứu để hỗ trợ việc ôn tập tốt hơn.",
    intro:
      "Nghiên cứu của đề tài đi từ khảo sát nhu cầu người học đến xây dựng kho tri thức y văn số hóa, phát triển công cụ hỏi đáp có tài liệu tham khảo và đánh giá thực nghiệm trong bối cảnh đào tạo Y học dự phòng tại Việt Nam.",
    photo: {
      src: "/images/medical/vietnam-preventive-medicine-lab.webp",
      alt: "Chuyên gia Y học dự phòng phân tích bản đồ giám sát dịch tễ học và dữ liệu bệnh truyền nhiễm",
      caption:
        "Nghiên cứu giám sát dịch tễ học thực địa kết hợp phân tích dữ liệu lớn — trọng tâm năng lực của Bác sĩ Y học dự phòng.",
    },
    sections: [
      {
        id: "nhu-cau",
        title: "Khảo sát năng lực số và hành vi ôn tập",
        paragraphs: [
          "Khảo sát năng lực số, thói quen ôn tập và mức độ sẵn sàng sử dụng AI là cơ sở xây dựng yêu cầu. Đối tượng nghiên cứu gồm sinh viên YHDP năm cuối và bác sĩ YHDP mới tốt nghiệp trên toàn quốc.",
          "Kết quả khảo sát phục vụ trực tiếp cho việc thiết kế kiến trúc hệ thống, giao diện di động và phương pháp sư phạm y khoa phù hợp.",
        ],
      },
      {
        id: "hoc-lieu",
        title: "Chuẩn hóa 54 vấn đề cốt lõi & Ngân hàng câu hỏi",
        paragraphs: [
          "Thuyết minh định hướng hệ thống hóa 54 vấn đề cốt lõi, liên kết nội dung với nguồn học liệu giáo trình ĐHYHN và mục tiêu chuẩn năng lực Bộ Y tế. Mỗi câu hỏi đều có đáp án, giải thích, tài liệu tham khảo và mức độ từ ghi nhớ đến vận dụng.",
          "Quy mô đề tài hướng tới 1.000–1.500 câu hỏi chuẩn hóa và tối thiểu 300 câu hỏi cốt lõi đã qua 2 vòng thẩm định độc lập mù đôi.",
        ],
      },
      {
        id: "kiem-chung",
        title: "Hỏi đáp kèm tài liệu tham khảo",
        paragraphs: [
          "Dự án hướng tới công cụ giúp tìm tài liệu liên quan đến câu hỏi và giải thích nội dung ôn tập. Người học cần mở nguồn tham khảo để kiểm tra; câu trả lời tự động vẫn có thể thiếu hoặc sai.",
          "Theo kế hoạch, câu hỏi cần được chuyên gia xem xét qua hai vòng độc lập trước khi phê duyệt. Nhóm nghiên cứu sẽ đánh giá chất lượng câu hỏi và mức độ thống nhất giữa các chuyên gia.",
        ],
      },
      {
        id: "thi-diem",
        title: "Đánh giá việc học và khả năng sử dụng thực tế",
        paragraphs: [
          "Thiết kế nghiên cứu can thiệp bán thực nghiệm có nhóm đối chứng song song nhằm đánh giá sự thay đổi về điểm số, khả năng ghi nhớ dài hạn và mức độ tự tin trước kỳ thi sát hạch.",
          "Nghiên cứu dự kiến xem người học có dễ sử dụng không, việc ôn tập thay đổi như thế nào và cơ sở đào tạo có thể duy trì công cụ ra sao. Đây là kế hoạch đánh giá, chưa phải kết quả đã được xác nhận.",
        ],
      },
    ],
    action: { to: "/ve-chung-toi", label: "Tìm hiểu phạm vi dự án" },
  },
  students: {
    title: "Ôn tập có kế hoạch, học đến khi hiểu.",
    intro:
      "Dành cho sinh viên Y học dự phòng năm cuối và bác sĩ YHDP mới tốt nghiệp đang hệ thống kiến thức, luyện tập và chuẩn bị cho kỳ kiểm tra năng lực hành nghề.",
    photo: {
      src: "/images/medical/vietnam-medical-training.webp",
      alt: "Sinh viên y khoa và bác sĩ nội trú thảo luận ca lâm sàng qua hồ sơ bệnh án và phim chụp CT",
      caption:
        "Tự học có định hướng: tra cứu tài liệu y văn chính thống và rèn luyện phản xạ dịch tễ học.",
    },
    sections: [
      {
        id: "bat-dau",
        title: "Bắt đầu từ một trọng tâm rõ ràng",
        paragraphs: [
          "Chọn học phần muốn tập trung, xem phần nội dung có sẵn và bắt đầu một phiên học vừa sức. Bài đánh giá đầu vào có thể giúp hình dung điểm mạnh, điểm cần ôn; kết quả minh họa không thay thế đánh giá năng lực thực tế.",
        ],
      },
      {
        id: "mot-phien",
        title: "Một phiên học có thể diễn ra như thế nào?",
        items: [
          "Ôn các thẻ đến hạn để nhắc lại kiến thức đã gặp.",
          "Luyện một bộ câu hỏi theo học phần hoặc nhóm nội dung.",
          "Đọc lời giải và mở đúng đoạn nguồn khi cần đối chiếu.",
          "Ghi lại điều chưa rõ trong sổ tay hoặc hỏi thêm tại mục Hỏi đáp học tập.",
          "Nhìn lại kết quả, chọn nội dung tiếp theo phù hợp với thời gian của mình.",
        ],
      },
      {
        id: "thi-thu",
        title: "Tách thời gian học và thời gian thi thử",
        paragraphs: [
          "Trong luyện tập, phản hồi giúp bạn sửa cách hiểu. Trong thi thử, hãy tập trung tự làm bài, quản lý thời gian và đánh dấu câu muốn xem lại. Phần giải thích và đối chiếu chỉ được xem sau khi kết thúc phiên thi.",
          "Điểm thi thử là thông tin phục vụ ôn tập. Nền tảng không cấp chứng chỉ hành nghề, không tổ chức kỳ kiểm tra chính thức và không bảo đảm kết quả thi của người sử dụng.",
        ],
      },
      {
        id: "luu-y",
        title: "Sử dụng phần hỏi đáp khi ôn tập",
        paragraphs: [
          "Đọc trích dẫn, kiểm tra cách lập luận và báo lại nội dung đáng ngờ. Không đưa thông tin định danh người bệnh vào câu hỏi. Các ca học tập và ví dụ chỉ phục vụ đào tạo, không dùng để quyết định chẩn đoán hoặc điều trị cho một người bệnh cụ thể.",
          "Ở chế độ trải nghiệm, dữ liệu lưu trong trình duyệt. Bạn có thể thử các thao tác bằng dữ liệu mẫu mà không cần cung cấp thông tin cá nhân.",
        ],
      },
    ],
    action,
  },
  lecturers: {
    title: "Giữ vai trò chuyên môn trong từng học liệu.",
    intro:
      "Không gian dành cho giảng viên và chuyên gia được thiết kế để kết nối biên soạn, thẩm định và theo dõi học tập. Việc phát triển các công cụ cần đi cùng quy trình chuyên môn và phân quyền rõ ràng.",
    photo: {
      src: "/images/medical/vietnam-doctor-consult.webp",
      alt: "Giảng viên lâm sàng hướng dẫn bác sĩ trẻ phân tích phác đồ điều trị và dự phòng",
      caption:
        "Giảng viên và chuyên gia y khoa đồng hành, đảm bảo tính chuẩn xác cho từng học liệu.",
    },
    sections: [
      {
        id: "bien-soan",
        title: "Biên soạn từ mục tiêu năng lực",
        paragraphs: [
          "Nội dung cần gắn với vấn đề cốt lõi, học phần và nguồn tham khảo. Một câu hỏi hữu ích phải có đáp án, giải thích lựa chọn, mức nhận thức và căn cứ để chuyên gia đối chiếu. AI có thể hỗ trợ tạo bản nháp, không tự xuất bản câu vào đề thi.",
        ],
      },
      {
        id: "tham-dinh",
        title: "Hai vòng thẩm định độc lập",
        paragraphs: [
          "Theo định hướng dự án, câu hỏi đưa vào đề thi thử cần thuộc nhóm đã được hai vòng chuyên gia thẩm định và phê duyệt. Ý kiến duyệt, yêu cầu sửa hoặc loại bỏ cần được ghi lại cùng phiên bản nội dung.",
          "Bản trải nghiệm có hai danh tính thẩm định để thử quy trình. Quyết định trong chế độ này chỉ cập nhật dữ liệu minh họa trên trình duyệt, không phải kết quả thẩm định học liệu chính thức.",
        ],
      },
      {
        id: "dong-hanh",
        title: "Theo dõi để hỗ trợ người học",
        paragraphs: [
          "Kết quả theo nhóm năng lực, chủ đề và mức nhận thức giúp giảng viên nhận diện nơi cần hỗ trợ. Phân tích chỉ có ý nghĩa khi đúng phạm vi lớp, đủ dữ liệu và có thông tin về số người tham gia.",
          "Bạn có thể thử quản lý lớp, lịch thi và kết quả bằng dữ liệu mẫu. Dữ liệu này chưa kết nối với hồ sơ hay kết quả học tập của nhà trường.",
        ],
      },
      {
        id: "phan-quyen",
        title: "Mỗi vai trò, một trách nhiệm",
        items: [
          "Người học: học, luyện tập, hỏi đáp và xem kết quả của mình.",
          "Chuyên gia: đối chiếu nguồn và thẩm định nội dung được phân công.",
          "Giảng viên: tổ chức, theo dõi hoạt động trong phạm vi được cấp quyền.",
          "Quản trị và cán bộ quản lý: vận hành, theo dõi và xem báo cáo theo phạm vi được phân quyền.",
        ],
      },
    ],
    action,
  },
  principles: {
    title: "Hỏi để hiểu bài, đọc nguồn để kiểm tra.",
    intro:
      "Phần hỏi đáp sử dụng trí tuệ nhân tạo (AI) để hỗ trợ giải thích kiến thức Y học dự phòng. Bạn chỉ cần nhập điều chưa hiểu bằng lời của mình. Giá trị của một câu trả lời nằm ở căn cứ, cách giải thích và việc biết khi nào cần dừng lại.",
    sections: [
      {
        id: "kiem-tra-nguon",
        title: "Bắt đầu từ nguồn học liệu",
        paragraphs: [
          "Câu trả lời có trích dẫn cần cho phép mở được đúng tài liệu hoặc đoạn liên quan. Đọc nguồn để xác định nội dung có thực sự hỗ trợ kết luận hay không. Dẫn nguồn không loại bỏ hoàn toàn nguy cơ hiểu sai hoặc trích dẫn sai.",
        ],
      },
      {
        id: "gioi-han",
        title: "Nói rõ khi chưa đủ căn cứ",
        paragraphs: [
          "Khi câu hỏi chưa rõ, hệ thống nên hỏi lại. Khi thiếu tài liệu phù hợp, hệ thống cần thể hiện giới hạn thay vì thêm thông tin không thể kiểm chứng. Người học có thể báo lại câu trả lời chưa chính xác để được xem xét.",
        ],
      },
      {
        id: "tu-duy",
        title: "Dùng phản hồi để tự giải thích lại",
        paragraphs: [
          "Thử nêu cách bạn hiểu trước khi xem giải thích. Sau khi đọc, hãy nói lại điểm khác biệt giữa các lựa chọn và tìm đoạn nguồn phù hợp. Mục tiêu là củng cố cách lập luận, không chỉ nhận một đáp án.",
        ],
      },
      {
        id: "an-toan",
        title: "Giữ phạm vi học tập",
        items: [
          "Không sử dụng câu trả lời để kê đơn hay quyết định xử trí người bệnh thực tế.",
          "Không nhập tên, hồ sơ hoặc thông tin có thể nhận diện người bệnh.",
          "Không sử dụng Hỏi đáp học tập để giải đáp trong phiên thi thử.",
          "Phân biệt học liệu minh họa, nội dung đang thẩm định và nội dung đã được phê duyệt.",
        ],
      },
    ],
    action,
  },
  help: {
    title: "Tìm đúng bước để tiếp tục học.",
    intro:
      "Hướng dẫn sử dụng bản trải nghiệm: đăng nhập thử, chọn học phần, mở nguồn, ôn tập và xử lý dữ liệu trên trình duyệt.",
    sections: [
      {
        id: "trai-nghiem",
        title: "Vào bản trải nghiệm",
        paragraphs: [
          "Mở trang đăng nhập, chọn phần trải nghiệm giao diện và một vai trò. Dữ liệu mẫu giúp thử thao tác mà không kết nối hệ thống thật. Chọn vai trò minh họa không cấp quyền vào hệ thống thật.",
        ],
      },
      {
        id: "hoc-phan",
        title: "Chọn và tìm học phần",
        paragraphs: [
          "Ở mục Học phần, dùng ô tìm kiếm hoặc bộ lọc để chọn nội dung. Học phần ghi “Đang xây dựng” chưa có học liệu để học đầy đủ. Bạn vẫn có thể xem phạm vi dự kiến trước khi chọn nội dung đang sẵn có.",
        ],
      },
      {
        id: "nguon",
        title: "Mở nguồn và báo lỗi",
        paragraphs: [
          "Khi lời giải có trích dẫn, chọn nhãn nguồn để mở phần đối chiếu. Nếu đoạn nguồn không phù hợp, ghi rõ nội dung đang xem và vấn đề gặp phải khi báo lỗi. Học liệu mẫu chưa qua thẩm định cần được đọc như ví dụ giao diện.",
        ],
      },
      {
        id: "du-lieu",
        title: "Khi dữ liệu thay đổi hoặc không còn",
        paragraphs: [
          "Dữ liệu trải nghiệm nằm trên trình duyệt hiện tại. Xóa dữ liệu trình duyệt, đổi thiết bị hoặc sử dụng chế độ riêng tư có thể làm mất tiến độ mẫu. Trong chế độ kết nối máy chủ, phiên làm việc và dữ liệu phụ thuộc hệ thống đã được triển khai.",
        ],
      },
    ],
    action: { to: "/faq", label: "Đọc câu hỏi thường gặp" },
  },
  security: {
    title: "An toàn là một phần của thiết kế.",
    intro:
      "Dự án đặt ra yêu cầu về phân quyền, bảo vệ dữ liệu và kiểm soát nội dung AI. Trang này phân biệt các nguyên tắc thiết kế với điều đã có thể thử trong giao diện.",
    sections: [
      {
        id: "tai-khoan",
        title: "Phân quyền theo công việc",
        paragraphs: [
          "Mỗi người chỉ được xem và thực hiện những công việc thuộc vai trò được cấp. Chọn một vai trò trong bản trải nghiệm chỉ giúp thử thao tác bằng dữ liệu mẫu, không cấp quyền truy cập dữ liệu thật.",
        ],
      },
      {
        id: "du-lieu",
        title: "Sử dụng dữ liệu đúng mục đích",
        paragraphs: [
          "Hoạt động học tập và tham gia nghiên cứu cần được giải thích riêng. Trong thiết kế, đồng ý dùng dịch vụ không đồng nghĩa đồng ý sử dụng dữ liệu cho nghiên cứu. Người học cần biết dữ liệu nào được ghi nhận và cách yêu cầu hỗ trợ.",
        ],
      },
      {
        id: "noi-dung",
        title: "Kiểm soát nội dung trước và sau phản hồi",
        paragraphs: [
          "Định hướng AI của dự án gồm kiểm tra phạm vi câu hỏi, tìm tài liệu liên quan, đối chiếu nguồn và kiểm chứng phản hồi. Chuyên gia tiếp tục giữ vai trò thẩm định. Không tuyên bố hệ thống không bao giờ sai hoặc thay thế người làm chuyên môn.",
        ],
      },
      {
        id: "xac-minh",
        title: "Những điều cần kiểm tra khi triển khai",
        paragraphs: [
          "An toàn hạ tầng, sao lưu, nhật ký, kiểm thử quyền truy cập và năng lực phục vụ là các hạng mục cần xác minh trên môi trường vận hành. Trang giới thiệu không phải chứng nhận an toàn thông tin hoặc xác nhận hệ thống đã được kiểm định.",
          "Bản trải nghiệm dùng dữ liệu mẫu lưu trên trình duyệt. Không đưa hồ sơ người bệnh hoặc dữ liệu cá nhân nhạy cảm vào phần thử giao diện.",
        ],
      },
    ],
    action: { to: "/quyen-rieng-tu", label: "Xem cách sử dụng dữ liệu" },
  },
  privacy: {
    title: "Dữ liệu của bạn được dùng như thế nào?",
    intro:
      "Thông tin dành cho bản giao diện đang phát triển, cập nhật ngày 16/10/2026. Quy trình và chính sách của hệ thống vận hành chính thức cần được công bố khi triển khai.",
    sections: [
      {
        id: "trai-nghiem",
        title: "Trong chế độ trải nghiệm",
        paragraphs: [
          "Vai trò mẫu, câu trả lời, thẻ ôn, tiến độ, phản ánh mẫu và một số tùy chọn được lưu trong bộ nhớ trình duyệt. Chế độ này không gọi mô hình AI hoặc ghi dữ liệu lên máy chủ dự án.",
          "Dữ liệu có thể bị mất khi xóa bộ nhớ trình duyệt hoặc đổi thiết bị. Không sử dụng hồ sơ người bệnh, thông tin định danh thật hoặc dữ liệu nhạy cảm để thử chức năng.",
        ],
      },
      {
        id: "ket-noi",
        title: "Khi kết nối hệ thống thật",
        paragraphs: [
          "Thông tin tài khoản, phiên đăng nhập và kết quả học tập sẽ được xử lý theo hệ thống máy chủ đã triển khai. Trước khi sử dụng, người học cần được thông báo về mục đích, phạm vi, thời gian lưu trữ và kênh liên hệ liên quan.",
          "Người học đăng nhập bằng mã kích hoạt; cán bộ dùng email và mật khẩu. Giao diện này không cung cấp đăng nhập Google hoặc Apple.",
        ],
      },
      {
        id: "nghien-cuu",
        title: "Đồng ý tham gia nghiên cứu là lựa chọn riêng",
        paragraphs: [
          "Theo định hướng dự án, hoạt động đánh giá học tập và nghiên cứu cần có quy trình thông tin, đồng ý và quản lý dữ liệu phù hợp. Không tự suy ra việc đồng ý nghiên cứu chỉ vì người dùng tạo tài khoản hoặc làm bài.",
        ],
      },
      {
        id: "quan-ly",
        title: "Quản lý dữ liệu trải nghiệm",
        paragraphs: [
          "Bạn có thể xem các mục liên quan trong Profile và dùng chức năng quản lý dữ liệu trải nghiệm. Việc xóa chỉ tác động đến dữ liệu được xử lý trong chế độ tương ứng, không phải xác nhận đã xóa mọi bản sao trên một hệ thống vận hành khác.",
        ],
      },
    ],
  },
  terms: {
    title: "Điều kiện sử dụng bản trải nghiệm.",
    intro:
      "DocPrep YHDP phục vụ ôn luyện và nghiên cứu phát triển nền tảng hỗ trợ học tập. Nội dung dưới đây giúp sử dụng đúng phạm vi của bản trải nghiệm hiện tại.",
    sections: [
      {
        id: "muc-dich",
        title: "Phạm vi sử dụng",
        paragraphs: [
          "Sử dụng để tìm hiểu giao diện, thực hành các luồng ôn tập và góp ý phát triển sản phẩm. Bản trải nghiệm không tổ chức kỳ kiểm tra hành nghề chính thức, không cấp chứng chỉ và không bảo đảm kết quả thi.",
        ],
      },
      {
        id: "noi-dung",
        title: "Trạng thái học liệu và kết quả",
        paragraphs: [
          "Nội dung được gắn nhãn minh họa hoặc chưa thẩm định không phải học liệu chính thức. Các số liệu minh họa không phải kết quả nghiên cứu. Mục tiêu trong thuyết minh không được hiểu là sản phẩm đã hoàn thành.",
        ],
      },
      {
        id: "trach-nhiem",
        title: "Sử dụng có trách nhiệm",
        items: [
          "Giữ câu hỏi và tình huống trong phạm vi học tập.",
          "Không tải lên dữ liệu người bệnh hoặc chia sẻ thông tin đăng nhập.",
          "Kiểm chứng giải thích của AI bằng nguồn phù hợp.",
          "Không sử dụng kết quả thi thử như chứng nhận năng lực hành nghề.",
        ],
      },
      {
        id: "cap-nhat",
        title: "Thay đổi trong quá trình phát triển",
        paragraphs: [
          "Giao diện, phạm vi dữ liệu và chức năng có thể được điều chỉnh sau rà soát chuyên môn và phản hồi. Điều kiện sử dụng chính thức, đơn vị vận hành và kênh hỗ trợ sẽ cần được xác nhận khi hệ thống được triển khai.",
        ],
      },
    ],
  },
  cookies: {
    title: "Bộ nhớ trình duyệt và dữ liệu trải nghiệm.",
    intro:
      "Trình duyệt ghi nhớ lựa chọn và tiến độ học mẫu trên thiết bị này. Bạn có thể mất dữ liệu đó khi xóa dữ liệu trang hoặc chuyển sang thiết bị khác.",
    sections: [
      {
        id: "luu-tru",
        title: "Những gì được ghi nhớ",
        paragraphs: [
          "Bộ nhớ cục bộ lưu vai trò trải nghiệm, lựa chọn học phần, dữ liệu mẫu và các tùy chọn tương ứng. Một số trạng thái phiên hoặc ý định thao tác được quản lý để hỗ trợ quay lại công việc đang làm.",
        ],
      },
      {
        id: "phien",
        title: "Phiên đăng nhập",
        paragraphs: [
          "Trong bản trải nghiệm, trình duyệt ghi nhớ vai trò bạn đã chọn để bạn tiếp tục thao tác. Đăng nhập bằng tài khoản thật cần hệ thống được kết nối và tài khoản được cấp.",
        ],
      },
      {
        id: "xoa",
        title: "Khi xóa bộ nhớ",
        paragraphs: [
          "Xóa dữ liệu trang trong trình duyệt có thể đặt lại vai trò, tiến độ và nội dung mẫu đã nhập. Chế độ duyệt riêng tư hoặc chặn lưu trữ cũng có thể làm các trạng thái không được giữ lại.",
        ],
      },
      {
        id: "ben-thu-ba",
        title: "Dịch vụ bên ngoài",
        paragraphs: [
          "Bản trải nghiệm không gửi câu hỏi đến mô hình AI. Ảnh minh họa và linh vật được phục vụ cùng giao diện. Khi kết nối backend thật, thông tin sử dụng dữ liệu cần được cập nhật trước khi vận hành.",
        ],
      },
    ],
  },
  accessibility: {
    title: "Một giao diện dễ tiếp cận hơn.",
    intro:
      "Khả năng tiếp cận được xem xét trong quá trình phát triển, từ đọc nội dung tiếng Việt đến thao tác bằng bàn phím và sử dụng trên điện thoại. Đây là định hướng và mô tả tính năng, chưa phải chứng nhận tuân thủ.",
    sections: [
      {
        id: "dieu-huong",
        title: "Điều hướng và bàn phím",
        paragraphs: [
          "Liên kết bỏ qua điều hướng giúp đi thẳng đến nội dung. Nút và liên kết có trạng thái focus; các tab minh họa hỗ trợ phím mũi tên, Home và End. Cửa sổ đối thoại có thao tác đóng bằng Escape.",
        ],
      },
      {
        id: "noi-dung",
        title: "Đọc nội dung rõ ràng",
        paragraphs: [
          "Giao diện sử dụng phông có dấu tiếng Việt, cấu trúc tiêu đề theo nội dung và độ dài dòng phù hợp. Ảnh có mô tả ngữ cảnh; các biểu tượng trang trí không thay thế nhãn chữ của chức năng quan trọng.",
        ],
      },
      {
        id: "chuyen-dong",
        title: "Kiểm soát chuyển động",
        paragraphs: [
          "Phần minh họa tự chuyển có nút bật/dừng và tạm dừng khi người dùng tương tác. Khi thiết bị yêu cầu giảm chuyển động, hiệu ứng dịch chuyển và tự chuyển được giảm hoặc tắt.",
        ],
      },
      {
        id: "phan-hoi",
        title: "Tiếp tục kiểm tra và cải thiện",
        paragraphs: [
          "Cần tiếp tục kiểm thử với công nghệ hỗ trợ và các tình huống sử dụng thực tế. Nếu gặp nội dung khó đọc hoặc thao tác không tiếp cận được, hãy ghi rõ trang, thiết bị và bước gặp vấn đề để nhóm phát triển xem xét.",
        ],
      },
    ],
    action: { to: "/lien-he", label: "Chuẩn bị phản hồi về giao diện" },
  },
};
