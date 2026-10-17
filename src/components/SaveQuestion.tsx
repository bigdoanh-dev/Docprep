import { ReportIssue } from "./ReportIssue";
// The approved scope removes saved questions. Existing content entry points now expose reporting.
export function SaveQuestion(props: {
  id: string;
  title: string;
  detail?: string;
  source?: string;
}) {
  return (
    <ReportIssue
      id={props.id.replace(/^card:/, "")}
      title={props.title}
      target={props.id.startsWith("card:") ? "card" : "question"}
    />
  );
}
