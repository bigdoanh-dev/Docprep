/** Validate the entire opening window before persisting or publishing an assignment. */
export function scheduleError(
  start: string,
  end: string,
  minutes: number,
): string | null {
  const from = Date.parse(start),
    to = Date.parse(end);
  if (!Number.isFinite(from) || !Number.isFinite(to))
    return "Nhập đầy đủ ngày và giờ mở bài, kết thúc.";
  if (!Number.isInteger(minutes) || minutes < 10 || minutes > 240)
    return "Thời lượng phải từ 10 đến 240 phút.";
  if (to <= from || to - from < minutes * 60000)
    return "Khung mở bài phải dài ít nhất bằng thời lượng và kết thúc sau bắt đầu.";
  return null;
}
