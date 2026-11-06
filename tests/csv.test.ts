import { test } from "node:test";
import assert from "node:assert/strict";
import { parseUserCsv } from "../src/features/management/csv.ts";
test("CSV accepts BOM, CRLF, quoted commas, escaped quotes and multiline fields", () => {
  const result = parseUserCsv(
    '\uFEFFdisplay_name,organisation_code,audience\r\n"Nguyễn, A",CSDT-A,student\r\n"B ""C""\nD",CSDT-B,graduate',
  );
  assert.equal(result.errors.length, 0);
  assert.equal(result.rows[0].display_name, "Nguyễn, A");
  assert.equal(result.rows[1].display_name, 'B "C"\nD');
});
test("CSV refuses missing headings and an unclosed quoted record", () => {
  assert.equal(parseUserCsv("name,school\nA,B").errors[0].row, 1);
  assert.ok(
    parseUserCsv('display_name,organisation_code,audience\n"A,B,student').errors
      .length,
  );
});
test("CSV reports invalid audience without silently accepting the row", () => {
  const r = parseUserCsv(
    "display_name,organisation_code,audience\nA,CSDT-A,doctor\nB,CSDT-B,student",
  );
  assert.equal(r.errors[0].row, 2);
  assert.equal(r.rows.length, 1);
});
