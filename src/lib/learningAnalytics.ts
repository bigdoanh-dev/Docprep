export const BLOOM = [
  "Ghi nhớ",
  "Hiểu",
  "Vận dụng",
  "Phân tích",
  "Đánh giá",
  "Sáng tạo",
];
export type AssessedAnswer = { question_id: string; correct: boolean };
export type QuestionMetadata = {
  id: string;
  bloom_level: number;
  competency_code: string;
};
export type GroupMetadata = {
  id: number;
  short_name: string;
  issues: { id: number }[];
};
export function groupForQuestion(q: QuestionMetadata, groups: GroupMetadata[]) {
  const issue = /^CI-(\d+)$/.exec(q.competency_code);
  return issue
    ? groups.find((g) => g.issues.some((i) => i.id === Number(issue[1])))
    : q.competency_code === "FND"
      ? groups.find((g) => g.id === 1)
      : undefined;
}
export function summarizeAnswers(
  answers: AssessedAnswer[],
  questions: QuestionMetadata[],
  groups: GroupMetadata[],
) {
  const levels = BLOOM.map((label_vi, i) => ({
    level: i + 1,
    label_vi,
    correct: 0,
    total: 0,
  }));
  const specialties = groups.map((g) => ({
    module_id: `g${g.id}`,
    name: g.short_name,
    correct: 0,
    total: 0,
  }));
  const bloom_by_specialty = groups.map((g) => ({
    module_id: `g${g.id}`,
    name: g.short_name,
    levels: levels.map((l) => ({ ...l })),
  }));
  const lookup = new Map(questions.map((q) => [q.id, q]));
  answers.forEach((a) => {
    const q = lookup.get(a.question_id);
    if (!q) return;
    const level = levels[q.bloom_level - 1];
    if (level) {
      level.total++;
      level.correct += Number(a.correct);
    }
    const group = groupForQuestion(q, groups);
    const stat = specialties.find((s) => s.module_id === `g${group?.id}`);
    if (stat) {
      stat.total++;
      stat.correct += Number(a.correct);
      const groupLevel = bloom_by_specialty.find(
        (s) => s.module_id === stat.module_id,
      )?.levels[q.bloom_level - 1];
      if (groupLevel) {
        groupLevel.total++;
        groupLevel.correct += Number(a.correct);
      }
    }
  });
  return { levels, specialties, bloom_by_specialty };
}

export type AssessmentCount = { correct: number; total: number };
export type BloomSpecialty = {
  module_id: string;
  name: string;
  levels: (AssessmentCount & { level: number; label_vi: string })[];
};
export type AnalysisPerspective = "specialty" | "bloom";

/** Empty assessments stay unknown; an assessed all-wrong cell really is 0%. */
export function assessmentPercent(count: AssessmentCount): number | null {
  return count.total > 0
    ? Math.round(
        (Math.max(0, Math.min(count.correct, count.total)) / count.total) * 100,
      )
    : null;
}

/** Both perspectives share the same cells and stable IDs, including sparse live payloads. */
export function learningMatrix(
  groups: BloomSpecialty[],
  perspective: AnalysisPerspective,
) {
  const cells = groups.map((g) =>
    BLOOM.map((label, index) => {
      const count = g.levels.find((l) => l.level === index + 1);
      return {
        id: `${g.module_id}:${index + 1}`,
        moduleId: g.module_id,
        specialty: g.name,
        level: index + 1,
        bloom: label,
        correct: count?.correct ?? 0,
        total: count?.total ?? 0,
      };
    }),
  );
  return perspective === "specialty"
    ? {
        columns: BLOOM.map((label, i) => ({ id: String(i + 1), label })),
        rows: groups.map((g, i) => ({
          id: g.module_id,
          label: g.name,
          cells: cells[i],
        })),
      }
    : {
        columns: groups.map((g) => ({ id: g.module_id, label: g.name })),
        rows: BLOOM.map((label, i) => ({
          id: String(i + 1),
          label,
          cells: cells.map((row) => row[i]),
        })),
      };
}
