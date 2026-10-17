export type ImportRow = {
  display_name: string;
  organisation_code: string;
  audience: "student" | "graduate";
};
export function parseUserCsv(text: string): {
  rows: ImportRow[];
  errors: { row: number; message: string }[];
} {
  const records: string[][] = [];
  let row: string[] = [],
    value = "",
    quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') {
        value += '"';
        i++;
      } else quoted = !quoted;
    } else if (c === "," && !quoted) {
      row.push(value.trim());
      value = "";
    } else if ((c === "\n" || c === "\r") && !quoted) {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(value.trim());
      if (row.some(Boolean)) records.push(row);
      row = [];
      value = "";
    } else value += c;
  }
  row.push(value.trim());
  if (row.some(Boolean)) records.push(row);
  if (quoted)
    return {
      rows: [],
      errors: [
        { row: records.length + 1, message: "Dấu ngoặc kép không được đóng." },
      ],
    };
  const header = (records.shift() ?? []).map((v) => v.replace(/^\uFEFF/, ""));
  const required = ["display_name", "organisation_code", "audience"];
  if (required.some((k) => !header.includes(k)))
    return {
      rows: [],
      errors: [
        {
          row: 1,
          message: "Cần đủ cột display_name, organisation_code, audience.",
        },
      ],
    };
  const rows: ImportRow[] = [],
    errors: { row: number; message: string }[] = [];
  records.forEach((r, i) => {
    const name = r[header.indexOf("display_name")],
      school = r[header.indexOf("organisation_code")],
      audience = r[header.indexOf("audience")];
    if (!name || !school || !["student", "graduate"].includes(audience))
      errors.push({
        row: i + 2,
        message: "Thiếu tên/mã trường hoặc audience phải là student/graduate.",
      });
    else
      rows.push({
        display_name: name,
        organisation_code: school,
        audience: audience as ImportRow["audience"],
      });
  });
  return { rows, errors };
}
