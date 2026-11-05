import blueprint from "../blueprint.json";
import { BLOOM } from "../learningAnalytics";

export const PROGRESS_EXAM_ID = "progress-demo";
export const PROGRESS_EXAM_TITLE = "Đề thi thử tổng hợp";

// Synthetic, non-clinical scenarios for exercising every specialty × Bloom cell.
// These questions are demonstration fixtures, not a validated exam bank.
const tasks = [
  {
    stem: "Trong bảng theo dõi minh họa, ‘tỷ lệ hoàn thành’ được định nghĩa là số hồ sơ hoàn thành chia cho tổng số hồ sơ. Công thức nào đúng?",
    choices: [
      "Hoàn thành / tổng số × 100%",
      "Tổng số / hoàn thành × 100%",
      "Hoàn thành × tổng số",
      "Tổng số − hoàn thành",
    ],
    explanation:
      "Theo định nghĩa trong tình huống, tỷ lệ hoàn thành là số hồ sơ hoàn thành chia tổng số hồ sơ, nhân 100%.",
  },
  {
    stem: "Hai nhóm có cùng tỷ lệ hoàn thành 80%, nhưng số hồ sơ lần lượt là 10 và 100. Nhận định nào phù hợp?",
    choices: [
      "Cùng tỷ lệ nhưng số hồ sơ hoàn thành khác nhau: 8 và 80",
      "Hai nhóm đều hoàn thành 80 hồ sơ",
      "Nhóm 10 hồ sơ hoàn thành nhiều hơn",
      "Cùng tỷ lệ nghĩa là cùng số hồ sơ",
    ],
    explanation:
      "80% của 10 là 8; 80% của 100 là 80. Cần phân biệt tỷ lệ với số lượng tuyệt đối.",
  },
  {
    stem: "Một đợt theo dõi có 40 hồ sơ, trong đó 30 hồ sơ đã hoàn thành. Áp dụng công thức hoàn thành / tổng số × 100%, kết quả là?",
    choices: ["75%", "30%", "40%", "25%"],
    explanation: "30 / 40 × 100% = 75%.",
  },
  {
    stem: "Bảng theo dõi ghi nhóm A hoàn thành 18/20 hồ sơ, nhóm B hoàn thành 60/100 hồ sơ. Phân tích nào đúng?",
    choices: [
      "A có tỷ lệ cao hơn (90% so với 60%), B có số hồ sơ hoàn thành nhiều hơn",
      "B có tỷ lệ cao hơn vì 60 lớn hơn 18",
      "A hoàn thành nhiều hồ sơ hơn B",
      "Hai nhóm có cùng tỷ lệ hoàn thành",
    ],
    explanation:
      "18/20 = 90%, còn 60/100 = 60%. Số lượng và tỷ lệ phản ánh hai khía cạnh khác nhau.",
  },
  {
    stem: "Một báo cáo kết luận toàn bộ chương trình đạt yêu cầu sau khi chỉ kiểm tra các hồ sơ đã hoàn thành. Đánh giá nào hợp lý nhất?",
    choices: [
      "Chưa đủ cơ sở; cần kiểm tra cả hồ sơ chưa hoàn thành và cách chọn mẫu",
      "Kết luận chắc chắn đúng vì các hồ sơ được chọn đều hoàn thành",
      "Không cần biết tổng số hồ sơ",
      "Chỉ cần tăng số trang báo cáo",
    ],
    explanation:
      "Chọn riêng hồ sơ hoàn thành có thể tạo thiên lệch. Cần xem phạm vi dữ liệu và cách chọn mẫu trước khi kết luận.",
  },
  {
    stem: "Cần xây dựng kế hoạch theo dõi mới, đồng thời đo tỷ lệ hoàn thành và tìm nguyên nhân chậm. Phương án thiết kế nào đáp ứng cả hai mục tiêu?",
    choices: [
      "Lập danh sách toàn bộ hồ sơ, ghi trạng thái và thời điểm, thu thập nguyên nhân chậm rồi tổng hợp định kỳ",
      "Chỉ lưu hồ sơ đã hoàn thành",
      "Chỉ đếm số cuộc họp",
      "Chỉ ghi tổng số hồ sơ mà không ghi trạng thái",
    ],
    explanation:
      "Kế hoạch cần kết hợp dữ liệu trạng thái, thời gian và nguyên nhân để đáp ứng đồng thời hai mục tiêu theo dõi.",
  },
];

export const progressQuestions = blueprint.groups.flatMap((group) =>
  tasks.map((task, index) => {
    const offset = (group.id + index) % task.choices.length;
    const choices = task.choices.map(
      (_, i) => (i + offset) % task.choices.length,
    );
    return {
      id: `q-progress-g${group.id}-b${index + 1}`,
      stem: `[Minh họa · ${group.short_name} · ${BLOOM[index]}] ${task.stem}`,
      options: choices.map((choice, i) => ({
        key: "abcd"[i],
        text: task.choices[choice],
        correct: choice === 0,
        rationale:
          choice === 0 ? task.explanation : `Chưa phù hợp. ${task.explanation}`,
      })),
      explanation: task.explanation,
      competency_code: `CI-${group.issues[index % group.issues.length].id}`,
      exam_competency_component: 1,
      bloom_level: index + 1,
      difficulty: "trung_binh",
      sources: [] as string[],
    };
  }),
);
