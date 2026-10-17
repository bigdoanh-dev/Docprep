import { ProjectPage } from "../ProjectPage";
import { projectPages } from "../projectContent";
export function AboutPage() {
  return <ProjectPage content={projectPages.about} />;
}
