import type { Me } from "../../lib/api";

import { learnerAudienceNames } from "../../lib/learnerProfile";

export function LearnerProfilePanel({
  me,
  compact = false,
}: {
  me: Me;
  compact?: boolean;
}) {
  if (compact)
    return (
      <p className="profile-compact">
        <span>
          Nhóm người học:{" "}
          <strong>
            {learnerAudienceNames[me.audience] ?? "Chưa xác định"}
          </strong>
        </span>
        <span>{me.organisation || "Chưa có đơn vị"}</span>
      </p>
    );
  return (
    <section
      className="panel stack learner-account-profile"
      aria-labelledby="learner-profile-heading"
    >
      <div>
        <h2 id="learner-profile-heading">Hồ sơ người học</h2>
      </div>
      <dl className="learner-account-facts">
        <div>
          <dt>Nhóm người học</dt>
          <dd>{learnerAudienceNames[me.audience] ?? "Chưa xác định"}</dd>
        </div>
        <div>
          <dt>Chương trình ôn tập</dt>
          <dd>Y học dự phòng</dd>
        </div>
        <div>
          <dt>Trường / đơn vị</dt>
          <dd>{me.organisation || "Chưa có thông tin"}</dd>
        </div>
      </dl>
    </section>
  );
}
