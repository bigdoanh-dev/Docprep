import type { Me } from "../../lib/api";

import { learnerAudienceNames } from "../../lib/learnerProfile";

export function LearnerProfilePanel({ me }: { me: Me }) {
  return (
    <section
      className="panel stack learner-account-profile"
      aria-labelledby="learner-profile-heading"
    >
      <div>
        <h2 id="learner-profile-heading">Hồ sơ người học</h2>
        <p className="muted small">
          Dành cho hai nhóm người học: sinh viên Y học dự phòng năm cuối và bác sĩ
          Y học dự phòng mới ra trường.
        </p>
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
      <p className="muted small">
        Nhóm người học và đơn vị được cơ sở đào tạo cấp tài khoản quản lý.
      </p>
    </section>
  );
}
