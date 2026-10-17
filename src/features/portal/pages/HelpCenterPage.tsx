import { ProjectPage } from "../ProjectPage";
import { projectPages } from "../projectContent";
export function HelpCenterPage() {
  return <ProjectPage content={projectPages.help} />;
}
