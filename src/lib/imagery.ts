// One relevant photograph per competency group; stable while searching or filtering.
const modulePhotos: Record<number, string> = {
  1: "research-lab",
  2: "first-aid-training",
  3: "nutrition",
  4: "laboratory-microscope",
  5: "occupational-safety",
  6: "nursing-care",
  7: "counseling",
  8: "clinical-rounds",
};
export function modulePhoto(group: number | null) {
  return `/images/curated/${modulePhotos[group ?? 0] ?? "medical-students"}.webp`;
}
const topicPhotos: [RegExp, number][] = [
  [/dinh dưỡng|thực phẩm/i, 3],
  [/cấp cứu|sơ cứu/i, 2],
  [/truyền nhiễm|dịch tễ|ổ dịch/i, 4],
  [/nghề nghiệp|lao động/i, 5],
  [/tâm thần|hành vi/i, 7],
  [/giao tiếp|cộng tác/i, 8],
  [/gia đình|chăm sóc/i, 6],
];
export function topicPhoto(title: string) {
  return modulePhoto(
    topicPhotos.find(([pattern]) => pattern.test(title))?.[1] ?? 1,
  );
}
