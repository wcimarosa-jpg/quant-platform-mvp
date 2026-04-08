import './App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthGuard } from './components/AuthGuard';
import { LoginPage } from './pages/LoginPage';
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
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<AuthGuard><HomePage /></AuthGuard>} />
        <Route path="/projects/new" element={<AuthGuard><ProjectSetupPage /></AuthGuard>} />
        <Route path="/projects/:projectId/brief" element={<AuthGuard><BriefReviewPage /></AuthGuard>} />
        <Route path="/projects/:projectId/survey" element={<AuthGuard><SurveyBuilderPage /></AuthGuard>} />
        <Route path="/projects/:projectId/mapping" element={<AuthGuard><MappingPage /></AuthGuard>} />
        <Route path="/projects/:projectId/analysis" element={<AuthGuard><AnalysisPage /></AuthGuard>} />
        <Route path="/projects/:projectId/report" element={<AuthGuard><ReportingPage /></AuthGuard>} />
        <Route path="*" element={<AuthGuard><HomePage /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  );
}
