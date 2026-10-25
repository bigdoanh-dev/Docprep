import { Notifications } from "../features/workspace/Notifications";
import { PracticeHub } from "../features/workspace/PracticeHub";
import { PortalLayout } from "../features/portal/PortalLayout";
import { FaqPage } from "../features/portal/pages/FaqPage";
import { SecurityCompliancePage } from "../features/portal/pages/SecurityCompliancePage";
import { PrivacyPolicyPage } from "../features/portal/pages/PrivacyPolicyPage";
import { TermsOfServicePage } from "../features/portal/pages/TermsOfServicePage";
import { CookiePolicyPage } from "../features/portal/pages/CookiePolicyPage";
import { AccessibilityStatementPage } from "../features/portal/pages/AccessibilityStatementPage";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { LoadError, Loading } from "../components/Status";
import { Account } from "../features/auth/Account";
import { Consent } from "../features/auth/Consent";
import { Focus } from "../features/auth/Focus";
import { Login } from "../features/auth/Login";
import { CardBrowser } from "../features/cards/CardBrowser";
import { CardReview } from "../features/cards/CardReview";
import { Decks } from "../features/cards/Decks";
import { SessionCards } from "../features/cards/SessionCards";
import { Chat } from "../features/chat/Chat";
import { QuizChat } from "../features/chat/QuizChat";
import { Exam } from "../features/exams/Exam";
import { ExamRules, Exams } from "../features/exams/Exams";
import { AnswerReview, Results } from "../features/exams/Results";
import { Home } from "../features/home/Home";
import { Adapting } from "../features/learning/Adapting";
import { Calendar } from "../features/learning/Calendar";
import { Modules } from "../features/learning/Modules";
import { Session } from "../features/learning/Session";
import {
  PracticeSet,
  SessionPractice,
} from "../features/learning/SessionPractice";
import { StudyPlan } from "../features/learning/StudyPlan";
import { Unit } from "../features/learning/Unit";
import { Progress } from "../features/progress/Progress";
import { ProgressRhythm } from "../features/progress/ProgressRhythm";
import { api, type Me } from "../lib/api";
import {
  onConsentRequired,
  onSignedOut,
  onStaffSignedOut,
} from "../lib/client";
import { roleHome, setActor, useActor, type Role } from "./identity";
import { Shell } from "./Shell";
const Management = lazy(
  () => import("../features/management/ManagementWorkspace"),
);
const learning: [string, ReactNode][] = [
  ["/on-tap", <PracticeHub />],
  ["/thong-bao", <Notifications />],
  ["/dong-y", <Consent />],
  ["/chon-hoc-phan", <Focus />],
  ["/luyen-tap", <Modules />],
  ["/luyen-tap/bo-the", <Decks />],
  ["/luyen-tap/on-the", <CardReview />],
  ["/luyen-tap/duyet-the", <CardBrowser />],
  ["/luyen-tap/bo-cau/:setId", <PracticeSet />],
  ["/luyen-tap/:unitId", <Unit />],
  ["/phien", <Session />],
  ["/phien/the", <SessionCards />],
  ["/phien/luyen", <SessionPractice />],
  ["/phien/dieu-chinh", <Adapting />],
  ["/hoi-dap", <Chat />],
  ["/hoi-dap/tu-cau-hoi/:questionId", <QuizChat />],
  ["/thi-thu", <Exams />],
  ["/thi-thu/:formId/quy-dinh", <ExamRules />],
  ["/thi-thu/lam-bai/:attemptId", <Exam />],
  ["/thi-thu/ket-qua/:attemptId", <Results />],
  ["/thi-thu/ket-qua/:attemptId/:questionId", <AnswerReview />],
  ["/tien-do", <Progress />],
  ["/tien-do/nhip-hoc", <ProgressRhythm />],
  ["/lich-on", <Calendar />],
  ["/lo-trinh", <StudyPlan />],
];
function RoleGate({ roles }: { roles: Role[] }) {
  const actor = useActor();
  if (!actor) return <Navigate to="/dang-nhap" replace />;
  if (!roles.includes(actor.role))
    return (
      <Shell>
        <div className="access-denied">
          <h1>Không có quyền truy cập</h1>
          <p>Vai trò hiện tại không được mở khu vực này.</p>
          <Link className="btn" to={roleHome(actor.role)} viewTransition>
            Về không gian của bạn
          </Link>
        </div>
      </Shell>
    );
  return <Outlet />;
}
function RequireLogin({ demoSessionStarted }: { demoSessionStarted: boolean }) {
  const actor = useActor();
  const loc = useLocation();
  if (!actor || (actor.mode === "demo" && !demoSessionStarted)) {
    const next = `${loc.pathname}${loc.search}${loc.hash}`;
    return (
      <Navigate to={`/dang-nhap?next=${encodeURIComponent(next)}`} replace />
    );
  }
  return <Outlet />;
}
function LearnerGate() {
  const actor = useActor(),
    loc = useLocation(),
    navigate = useNavigate();
  const [gate, setGate] = useState<"loading" | "focus" | "open">("loading"),
    [error, setError] = useState("");
  const onConsent = loc.pathname === "/dong-y";
  useEffect(
    () =>
      onConsentRequired(() => {
        if (!onConsent)
          navigate(
            `/dong-y?next=${encodeURIComponent(loc.pathname + loc.search)}`,
            { replace: true },
          );
      }),
    [navigate, loc, onConsent],
  );
  useEffect(() => {
    if (!actor || onConsent) return;
    let alive = true;
    setError("");
    api.get<Me & { consent: { service_given_at: string | null } }>("/me").then(
      (me) => {
        if (!alive) return;
        if (actor.mode === "live" && actor.id !== me.pseudonym_id)
          setActor({ ...actor, id: me.pseudonym_id, name: me.display_name });
        if (!me.consent.service_given_at) {
          navigate("/dong-y", { replace: true });
          return;
        }
        setGate(me.diagnostic_prompt_dismissed ? "open" : "focus");
      },
      (e) => alive && setError(e.message),
    );
    return () => {
      alive = false;
    };
  }, [actor?.id, onConsent, navigate]);
  if (!actor) return <Navigate to="/dang-nhap" />;
  if (onConsent) return <Outlet />;
  if (error)
    return (
      <LoadError message={error} onRetry={() => window.location.reload()} />
    );
  if (gate === "loading") return <Loading />;
  if (gate === "focus" && loc.pathname !== "/chon-hoc-phan")
    return <Navigate to="/chon-hoc-phan" replace />;
  return <Outlet context={{ focusChosen: () => setGate("open") }} />;
}
function Entry() {
  const actor = useActor();
  if (!actor) return <Navigate to="/dang-nhap" replace />;
  if (actor.role !== "learner")
    return <Navigate to={roleHome(actor.role)} replace />;
  return <LearnerGate />;
}
export default function App() {
  const [demoSessionStarted, setDemoSessionStarted] = useState(false);
  useEffect(() => onSignedOut(() => setActor(null)), []);
  useEffect(() => onStaffSignedOut(() => setActor(null)), []);
  return (
    <BrowserRouter>
      <a className="skip-link" href="#main-content">
        Bỏ qua điều hướng
      </a>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route
            path="/dang-nhap"
            element={<Login onDemoStart={() => setDemoSessionStarted(true)} />}
          />
          <Route
            path="/quan-ly/dang-nhap"
            element={<Navigate to="/dang-nhap" replace />}
          />

          <Route
            element={<RequireLogin demoSessionStarted={demoSessionStarted} />}
          >
            {/* Static Portal Pages */}
            <Route element={<PortalLayout />}>
              <Route
                path="/gioi-thieu"
                element={<Navigate to="/dang-nhap" replace />}
              />
              <Route
                path="/khoa-hoc"
                element={<Navigate to="/tinh-nang" replace />}
              />
              <Route
                path="/courses"
                element={<Navigate to="/tinh-nang" replace />}
              />
              <Route
                path="/features"
                element={<Navigate to="/tinh-nang" replace />}
              />
              <Route
                path="/research"
                element={<Navigate to="/nghien-cuu" replace />}
              />
              <Route
                path="/about"
                element={<Navigate to="/ve-chung-toi" replace />}
              />
              <Route
                path="/thu-vien-anh"
                element={<Navigate to="/gioi-thieu" replace />}
              />
              <Route
                path="/media"
                element={<Navigate to="/gioi-thieu" replace />}
              />
              <Route
                path="/students"
                element={<Navigate to="/hoc-vien" replace />}
              />
              <Route
                path="/lecturers"
                element={<Navigate to="/giang-vien-gioi-thieu" replace />}
              />
              <Route
                path="/ai-learning"
                element={<Navigate to="/hoc-cung-ai" replace />}
              />
              <Route
                path="/tro-giup"
                element={<Navigate to="/faq" replace />}
              />
              <Route path="/help" element={<Navigate to="/faq" replace />} />
              <Route path="/faq" element={<FaqPage />} />
              <Route
                path="/contact"
                element={<Navigate to="/lien-he" replace />}
              />
              <Route path="/bao-mat" element={<SecurityCompliancePage />} />
              <Route
                path="/security"
                element={<Navigate to="/bao-mat" replace />}
              />
              <Route path="/quyen-rieng-tu" element={<PrivacyPolicyPage />} />
              <Route
                path="/legal/privacy"
                element={<Navigate to="/quyen-rieng-tu" replace />}
              />
              <Route path="/dieu-khoan" element={<TermsOfServicePage />} />
              <Route
                path="/legal/terms"
                element={<Navigate to="/dieu-khoan" replace />}
              />
              <Route path="/cookie" element={<CookiePolicyPage />} />
              <Route
                path="/legal/cookies"
                element={<Navigate to="/cookie" replace />}
              />
              <Route
                path="/tiep-can"
                element={<AccessibilityStatementPage />}
              />
              <Route
                path="/accessibility"
                element={<Navigate to="/tiep-can" replace />}
              />
            </Route>
            <Route element={<Entry />}>
              <Route element={<Shell />}>
                <Route path="/" element={<Home />} />
              </Route>
            </Route>
            <Route element={<RoleGate roles={["learner"]} />}>
              <Route element={<LearnerGate />}>
                <Route element={<Shell />}>
                  {learning.map(([path, element]) => (
                    <Route key={path} path={path} element={element} />
                  ))}
                </Route>
              </Route>
            </Route>
            <Route element={<RoleGate roles={["admin"]} />}>
              <Route element={<Shell />}>
                <Route path="/quan-tri/*" element={<Management />} />
              </Route>
            </Route>
            <Route element={<RoleGate roles={["ministry_viewer", "admin"]} />}>
              <Route element={<Shell />}>
                <Route path="/quan-ly/*" element={<Management />} />
              </Route>
            </Route>
            <Route
              element={
                <RoleGate roles={["learner", "admin", "ministry_viewer"]} />
              }
            >
              <Route element={<Shell />}>
                <Route path="/profile" element={<Account />} />
                <Route
                  path="/tai-khoan"
                  element={<Navigate to="/profile" replace />}
                />
              </Route>
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
function NotFound() {
  const actor = useActor();
  return (
    <div className="access-denied">
      <h1>Không tìm thấy trang</h1>
      <p>Đường dẫn này không thuộc không gian hiện tại.</p>
      <a
        className="btn primary"
        href={actor ? roleHome(actor.role) : "/dang-nhap"}
      >
        Quay về
      </a>
    </div>
  );
}
