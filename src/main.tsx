import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";

import { MotionConfig } from "motion/react";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";
import { FeedbackProvider } from "./components/ui/Feedback";
import "./styles/global.css";
import "./styles/tokens.css";
import "./styles/redesign.css";
import "./styles/portal.css";
import "./styles/refinements.css";
import "./styles/project.css";
import "./styles/landing-refresh.css";
import "./styles/mobile.css";
import "./styles/mobile-polish.css";
import "./styles/staff.css";
import "./styles/feedback.css";
import "./styles/tutor.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <FeedbackProvider>
        <App />
      </FeedbackProvider>
    </MotionConfig>
  </React.StrictMode>,
);
