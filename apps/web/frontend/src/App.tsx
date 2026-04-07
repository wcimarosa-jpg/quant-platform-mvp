import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { ProjectSetupPage } from './pages/ProjectSetupPage';
import { BriefReviewPage } from './pages/BriefReviewPage';
import { SurveyBuilderPage } from './pages/SurveyBuilderPage';
import { MappingPage } from './pages/MappingPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { ReportingPage } from './pages/ReportingPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/new" element={<ProjectSetupPage />} />
        <Route path="/projects/:projectId/brief" element={<BriefReviewPage />} />
        <Route path="/projects/:projectId/survey" element={<SurveyBuilderPage />} />
        <Route path="/projects/:projectId/mapping" element={<MappingPage />} />
        <Route path="/projects/:projectId/analysis" element={<AnalysisPage />} />
        <Route path="/projects/:projectId/report" element={<ReportingPage />} />
      </Routes>
    </BrowserRouter>
  );
}
