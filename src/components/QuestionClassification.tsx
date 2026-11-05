import blueprint from "../lib/blueprint.json";
import type { QuestionClassification as Classification } from "../lib/api";
import { BLOOM } from "../lib/learningAnalytics";

const DIFFICULTY: Record<string, string> = {
  de: "Dễ",
  trung_binh: "Trung bình",
  kho: "Khó",
};

export function QuestionClassification({
  metadata,
}: {
  metadata: Classification;
}) {
  const group = blueprint.groups.find(
    (g) =>
      `g${g.id}` === metadata.module_id ||
      g.short_name === metadata.module_name?.trim() ||
      g.name === metadata.module_name?.trim() ||
      g.issues.some(
        (i) =>
          i.id === metadata.core_issue_id ||
          i.name === metadata.core_issue_name?.trim(),
      ),
  );
  const issue = group?.issues.find(
    (i) =>
      i.id === metadata.core_issue_id ||
      i.name === metadata.core_issue_name?.trim(),
  );
  const specialty = metadata.module_name?.trim() || group?.short_name;
  const issueName = issue?.name || metadata.core_issue_name?.trim();
  const difficulty = metadata.difficulty_label?.trim();
  const bloom = metadata.bloom_level
    ? BLOOM[metadata.bloom_level - 1]
    : undefined;
  return (
    <dl className="question-classification" aria-label="Phân loại câu hỏi">
      <div>
        <dt>Mức độ câu hỏi</dt>
        <dd>
          {difficulty
            ? (DIFFICULTY[difficulty] ?? difficulty)
            : "Chưa phân loại"}
        </dd>
      </div>
      {bloom && (
        <div>
          <dt>Mức độ nhận thức</dt>
          <dd>{bloom}</dd>
        </div>
      )}
      <div>
        <dt>Đề mục</dt>
        <dd>{specialty || "Chưa phân loại"}</dd>
      </div>
      <div>
        <dt>Vấn đề</dt>
        <dd>{issueName || "Chưa phân loại"}</dd>
      </div>
    </dl>
  );
}
