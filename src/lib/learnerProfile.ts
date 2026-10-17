import type { Me } from "./api";

// These are the account audiences in NLHN-YHDP, not professional titles.
export const learnerAudienceNames: Record<Me["audience"], string> = {
  student: "Sinh viên",
  graduate: "Đã tốt nghiệp",
};
