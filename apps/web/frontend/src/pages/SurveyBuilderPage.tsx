import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, SectionNavigator, CheckpointBlock } from '../components/shared';

const SECTIONS = [
  { id: 'screener', label: 'Screener', status: 'complete' },
  { id: 'motivations', label: 'Motivations', status: 'complete' },
  { id: 'funnel', label: 'Purchase Funnel', status: 'needs_review' },
  { id: 'demographics', label: 'Demographics', status: 'complete' },
];

export function SurveyBuilderPage() {
  const { projectId } = useParams();
  const [activeSection, setActiveSection] = useState('screener');
  const [questions, setQuestions] = useState(
    'MOT_01: What factors are most important when choosing a product in this category?\nMOT_02: How often do you purchase products in this category?\nMOT_03: What would make you switch brands?',
  );

  return (
    <AppShell currentStage={3} projectId={projectId}>
      <PageHeader title="Survey Builder" subtitle="Step 3 of 6 — Build questionnaire from brief objectives" />
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 14 }}>
        <SectionNavigator sections={SECTIONS} activeId={activeSection} onSelect={setActiveSection} />
        <div className="card">
          <h3 style={{ textTransform: 'capitalize' }}>{activeSection.replace('_', ' ')}</h3>
          <textarea
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            rows={10}
            style={{ width: '100%', padding: 12, border: '1px solid var(--line)', borderRadius: 10, marginTop: 8, fontFamily: 'inherit', fontSize: 14 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button className="btn btn-secondary btn-sm">Rewrite for clarity</button>
            <button className="btn btn-secondary btn-sm">Align to objective</button>
            <button className="btn btn-secondary btn-sm">Suggest alternative</button>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <CheckpointBlock title="Publish Questionnaire" description="Lock the survey for data collection." status="pending" />
      </div>
    </AppShell>
  );
}
