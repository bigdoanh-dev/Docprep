// Display formats shared by the screens. No import here: the module runs as it is under Node for its tests.
// Dates are dd/mm/yyyy in the viewer's local time.

const pad = (n: number) => String(n).padStart(2, "0");

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// "37 giây", "2 phút", "2 phút 5 giây"
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m === 0 ? `${s} giây` : s === 0 ? `${m} phút` : `${m} phút ${s} giây`;
}

// Countdown as mm:ss
export function mmss(seconds: number): string {
  return `${pad(Math.floor(seconds / 60))}:${pad(seconds % 60)}`;
}

// "<1 phút", "6 phút", "3 giờ", "4 ngày": when a card comes back for a rating.
export function interval(seconds: number): string {
  if (seconds < 60) return "<1 phút";
  if (seconds < 3600) return `${Math.round(seconds / 60)} phút`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} giờ`;
  return `${Math.round(seconds / 86400)} ngày`;
}

// "45 ph", "1 g", "3 g 20 ph": study time, from minutes.
export function studyTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h === 0 ? `${m} ph` : m === 0 ? `${h} g` : `${h} g ${m} ph`;
}

// "86%" from 0.86; a share that does not exist yet is a dash, not a zero.
export function percent(share: number | null): string {
  return share === null ? "—" : `${Math.round(share * 100)}%`;
}

// "09/10" from the calendar day "2026-10-09", by its own digits: no time zone can move it.
export function dayMonth(isoDate: string): string {
  return `${isoDate.slice(8, 10)}/${isoDate.slice(5, 7)}`;
}
