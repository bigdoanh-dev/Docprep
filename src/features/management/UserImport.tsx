import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FileSpreadsheet,
  FileUp,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { useFeedback } from "../../components/ui/Feedback";
import { api } from "../../lib/api";
import { staffSession } from "../../lib/client";
import { saveFile } from "../auth/Account";
import { parseUserCsv } from "./csv";

const SAMPLE_CSV = `display_name,organisation_code,audience
Nguyễn Thu Hà,CSDT-A,student
Trần Minh Anh,CSDT-B,graduate
Lê Hoàng Nam,CSDT-C,student
Phạm Quốc Bảo,CSDT-D,graduate
Hoàng Thị Mai,CSDT-E,student`;

export function UserImport() {
  const actor = useActor()!,
    notify = useFeedback();

  const [text, setText] = useState(SAMPLE_CSV);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [issued, setIssued] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [showRawText, setShowRawText] = useState(false);

  const step3Ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (issued.length > 0 && step3Ref.current) {
      step3Ref.current.scrollIntoView({ behavior: "smooth", block: "start" });
      step3Ref.current.focus();
    }
  }, [issued]);

  const inspect = async () => {
    notify.dismiss?.();
    setBusy(true);
    setError("");
    setIssued([]);
    try {
      if (actor.mode === "demo") {
        const p = parseUserCsv(text);
        setPreview({
          ...p,
          batch_id: 1,
          rows_total: p.rows.length + p.errors.length,
          rows_valid: p.rows.length,
        });
        if (p.errors.length > 0) {
          notify(`Phát hiện ${p.errors.length} dòng không đúng định dạng.`, "info");
        } else {
          notify(`Kiểm tra thành công ${p.rows.length} dòng hợp lệ.`);
        }
      } else {
        if (!file) throw new Error("Vui lòng chọn tệp CSV trước khi bấm kiểm tra.");
        const form = new FormData();
        form.append("file", file);
        const r = await staffSession.fetch("/api/v1/admin/users/import", {
          method: "POST",
          body: form,
        });
        const d = await r.json();
        if (!r.ok) {
          throw new Error(
            d.error?.message_vi ??
              (r.status === 501
                ? "API nhập danh sách CSV hiện đang ở trạng thái chuẩn bị (501) trên máy chủ R1.0."
                : "Không thể nhập danh sách trên máy chủ.")
          );
        }
        setPreview({
          ...d,
          rows: d.sample,
          errors: d.errors.map((e: any) => ({
            row: e.row,
            message: e.message_vi,
          })),
        });
      }
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      notify(msg, "error");
    } finally {
      setBusy(false);
    }
  };

  const issueCodes = async () => {
    notify.dismiss?.();
    setBusy(true);
    try {
      if (actor.mode === "demo") {
        const generated = preview.rows.map((r: any, i: number) => ({
          ...r,
          code: `DEMO-ACT-${String(i + 1).padStart(4, "0")}`,
        }));
        setIssued(generated);
        notify("Đã tạo mã kích hoạt minh họa thành công.");
      } else {
        const result = await api.post<any>(
          `/admin/users/import/${preview.batch_id}/confirm`,
        );
        setIssued(result.codes);
        notify("Đã phát hành mã kích hoạt tài khoản thành công.");
      }
      setConfirmOpen(false);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      notify(msg, "error");
    } finally {
      setBusy(false);
    }
  };

  const loadSample = () => {
    notify.dismiss?.();
    setText(SAMPLE_CSV);
    setFile(null);
    setPreview(null);
    setIssued([]);
    setError("");
    notify("Đã nạp bộ dữ liệu CSV mẫu.");
  };

  const resetAll = () => {
    notify.dismiss?.();
    setFile(null);
    setText(SAMPLE_CSV);
    setPreview(null);
    setIssued([]);
    setError("");
  };

  const isStep1Done = preview !== null || issued.length > 0;
  const isStep2Done = issued.length > 0;
  const isStep3Done = issued.length > 0;

  return (
    <div className="user-import-page">
      <header className="import-header">
        <Link to="/quan-tri" className="import-back-link">
          <ArrowLeft size={15} />
          <span>Quay lại Vận hành</span>
        </Link>
        <h1>Cấp tài khoản theo CSV</h1>
      </header>

      {/* 3-Step Mobile Flow Indicator */}
      <div className="import-stepper" aria-label="Tiến trình cấp tài khoản">
        <div className={`step-item ${isStep1Done ? "completed" : "active"}`}>
          <span className="step-num">{isStep1Done ? "✓" : "1"}</span>
          <span className="step-name">Chọn tệp</span>
        </div>
        <div className={`step-line ${isStep1Done ? "active" : ""}`} />
        <div className={`step-item ${isStep2Done ? "completed" : preview ? "active" : ""}`}>
          <span className="step-num">{isStep2Done ? "✓" : "2"}</span>
          <span className="step-name">Kiểm tra</span>
        </div>
        <div className={`step-line ${isStep2Done ? "active" : ""}`} />
        <div className={`step-item ${isStep3Done ? "completed" : ""}`}>
          <span className="step-num">{isStep3Done ? "✓" : "3"}</span>
          <span className="step-name">Cấp mã</span>
        </div>
      </div>

      {/* Live Mode Notice */}
      {actor.mode === "live" && (
        <div className="live-api-warning-card">
          <FutureNotice release="api" name="API nhập danh sách CSV (/v1/admin/users/import)" />
          <p className="live-api-text">
            Theo kiến trúc R1.0, API nhập CSV người học đang trả mã HTTP 501. Ứng dụng không giả lập cấp mã thật trên môi trường máy chủ. Vui lòng sử dụng chế độ Trải nghiệm (Demo) để thử nghiệm.
          </p>
        </div>
      )}

      {/* When Step 3 is completed: Render Step 3 immediately at top */}
      {issued.length > 0 ? (
        <>
          <section
            ref={step3Ref}
            tabIndex={-1}
            className="import-step-card success-section"
            aria-labelledby="step3-heading"
          >
            <div className="step-card-title-row">
              <h2 id="step3-heading">3. Mã kích hoạt đã phát hành</h2>
              <span className="badge-valid">
                <CheckCircle2 size={13} />
                {issued.length} mã thành công
              </span>
            </div>

            <p className="issued-security-note">
              Mã kích hoạt chỉ hiển thị 1 lần. Vui lòng tải danh sách và bàn giao cho cơ sở đào tạo hoặc người học.
            </p>

            <div className="issued-codes-scroll">
              {issued.map((r, i) => (
                <div className="issued-code-row" key={i}>
                  <div className="issued-code-user">
                    <strong>{r.display_name}</strong>
                    <span>{r.organisation_code}</span>
                  </div>
                  <code className="issued-code-text">{r.code}</code>
                </div>
              ))}
            </div>

            <div className="issued-buttons-row">
              <button
                type="button"
                className="btn-secondary-outline"
                onClick={() =>
                  saveFile(
                    issued,
                    actor.mode === "demo"
                      ? "danh-sach-ma-kich-hoat-minh-hoa.json"
                      : "danh-sach-ma-kich-hoat.json",
                  )
                }
              >
                <Download size={14} />
                Tải danh sách mã (JSON)
              </button>
              <button
                type="button"
                className="btn-reset-import"
                onClick={resetAll}
              >
                Cấp danh sách mới
              </button>
            </div>
          </section>

          {/* Collapsible reference to the verified dataset */}
          <details className="past-steps-disclosure">
            <summary className="past-steps-summary">
              <span>Xem lại danh sách đã nạp ({issued.length} người)</span>
              <ChevronDown size={13} className="past-steps-arrow" />
            </summary>
            <div className="past-steps-content">
              <div className="preview-scroll-list">
                {issued.map((r: any, i: number) => (
                  <div className="preview-row-card" key={i}>
                    <div className="preview-row-info">
                      <strong>{r.display_name}</strong>
                      <span>{r.organisation_code}</span>
                    </div>
                    <span className="audience-tag">
                      {r.audience === "student" ? "Sinh viên" : "Tốt nghiệp"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </details>
        </>
      ) : (
        <>
          {/* STEP 1: Chọn tệp CSV */}
          <section className="import-step-card" aria-labelledby="step1-heading">
            <div className="step-card-title-row">
              <h2 id="step1-heading">1. Chọn tệp danh sách (.csv)</h2>
              {file && (
                <button type="button" className="btn-clear-file" onClick={resetAll}>
                  Đổi tệp
                </button>
              )}
            </div>

            <div className="file-select-box">
              <label className="btn-select-file">
                <FileUp size={16} />
                <span>{file ? file.name : "Chọn tệp CSV từ thiết bị"}</span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setFile(f);
                      setText(await f.text());
                      setPreview(null);
                      setIssued([]);
                      setError("");
                    }
                  }}
                />
              </label>

              <div className="file-guidance-group">
                <span className="file-format-guidance">
                  Bao gồm: Họ và tên, Cơ sở đào tạo, Nhóm người học (sinh viên / tốt nghiệp).
                </span>
                <details className="csv-spec-disclosure">
                  <summary className="csv-spec-summary">
                    <span>Quy cách tệp CSV</span>
                    <ChevronDown size={12} className="spec-summary-arrow" />
                  </summary>
                  <div className="csv-spec-content">
                    <p>• Cột bắt buộc: <code>display_name</code>, <code>organisation_code</code>, <code>audience</code></p>
                    <p>• Định dạng: Bảng mã UTF-8, dấu phẩy (<code>,</code>) phân cách</p>
                    <p>• Cột đối tượng: <code>student</code> (sinh viên) hoặc <code>graduate</code> (đã tốt nghiệp)</p>
                  </div>
                </details>
              </div>
            </div>

            {actor.mode === "demo" && (
              <div className="demo-helper-links">
                <button
                  type="button"
                  className="link-helper-btn"
                  onClick={loadSample}
                >
                  <RotateCcw size={12} />
                  Nạp dữ liệu mẫu
                </button>
                <span className="link-sep">·</span>
                <button
                  type="button"
                  className="link-helper-btn"
                  onClick={() => setShowRawText(!showRawText)}
                >
                  {showRawText ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  {showRawText ? "Ẩn nội dung CSV" : "Xem/Sửa nội dung CSV"}
                </button>
              </div>
            )}

            {showRawText && (
              <div className="raw-csv-container">
                <textarea
                  className="raw-csv-input"
                  rows={5}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    setPreview(null);
                    setIssued([]);
                  }}
                  placeholder="Nguyễn Thu Hà,CSDT-A,student..."
                />
              </div>
            )}

            <button
              type="button"
              className="btn-primary-mobile"
              onClick={inspect}
              disabled={busy || (!file && actor.mode === "live")}
            >
              <FileSpreadsheet size={15} />
              <span>{busy ? "Đang kiểm tra…" : "Kiểm tra danh sách"}</span>
            </button>

            {error && (
              <div className="import-error-banner" role="alert">
                <AlertCircle size={15} />
                <span>{error}</span>
              </div>
            )}
          </section>

          {/* STEP 2: Kết quả kiểm tra */}
          {preview && (
            <section className="import-step-card" aria-labelledby="step2-heading">
              <div className="step-card-title-row">
                <h2 id="step2-heading">2. Kết quả kiểm tra dữ liệu</h2>
              </div>

              <div className="inspection-result-badge">
                <span className="badge-valid">
                  <CheckCircle2 size={14} />
                  {preview.rows.length} dòng hợp lệ
                </span>
                {preview.errors.length > 0 && (
                  <span className="badge-invalid">
                    <AlertTriangle size={14} />
                    {preview.errors.length} dòng lỗi
                  </span>
                )}
              </div>

              {preview.errors.length > 0 && (
                <div className="import-errors-box">
                  <strong className="errors-box-title">Dòng cần chỉnh sửa:</strong>
                  {preview.errors.map((e: any, i: number) => (
                    <div className="error-item-line" key={i}>
                      <span className="error-item-row">Dòng {e.row}:</span>
                      <span className="error-item-msg">{e.message}</span>
                    </div>
                  ))}
                </div>
              )}

              {preview.rows.length > 0 && (
                <div className="preview-list-wrapper">
                  <span className="preview-caption">
                    Danh sách học viên hợp lệ ({preview.rows.length}):
                  </span>
                  <div className="preview-scroll-list">
                    {preview.rows.map((r: any, i: number) => (
                      <div className="preview-row-card" key={i}>
                        <div className="preview-row-info">
                          <strong>{r.display_name}</strong>
                          <span>{r.organisation_code}</span>
                        </div>
                        <span className="audience-tag">
                          {r.audience === "student" ? "Sinh viên" : "Tốt nghiệp"}
                        </span>
                      </div>
                    ))}
                  </div>

                  {actor.mode === "live" ? (
                    <div className="live-501-box">
                      <AlertTriangle size={14} />
                      <span>
                        Chức năng phát hành mã thật trên live đang chờ backend mở endpoint (HTTP 501).
                      </span>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary-mobile"
                      disabled={busy || preview.errors.length > 0 || preview.rows.length === 0}
                      onClick={() => {
                        notify.dismiss?.();
                        setConfirmOpen(true);
                      }}
                    >
                      Xác nhận cấp mã kích hoạt ({preview.rows.length} người)
                    </button>
                  )}
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* Confirmation Bottom Sheet */}
      <Sheet
        open={confirmOpen}
        onClose={() => !busy && setConfirmOpen(false)}
        title="Xác nhận cấp mã kích hoạt"
      >
        <div className="confirm-sheet-content">
          <div className="confirm-icon-box">
            <ShieldAlert size={24} />
          </div>
          <h3>Cấp {preview?.rows?.length ?? 0} mã kích hoạt</h3>
          <p>
            {actor.mode === "demo"
              ? "Hệ thống sẽ sinh mã kích hoạt minh họa độc lập trên trình duyệt để kiểm thử giao diện."
              : "Hệ thống sẽ tạo bản ghi học viên và cấp mã kích hoạt sử dụng một lần."}
          </p>
          <div className="confirm-sheet-buttons">
            <button
              className="btn-primary-mobile"
              onClick={issueCodes}
              disabled={busy}
            >
              {busy ? "Đang cấp mã…" : "Đồng ý cấp mã"}
            </button>
            <button
              className="btn-secondary-outline"
              onClick={() => setConfirmOpen(false)}
              disabled={busy}
            >
              Quay lại
            </button>
          </div>
          {error && <p className="warn">{error}</p>}
        </div>
      </Sheet>
    </div>
  );
}
