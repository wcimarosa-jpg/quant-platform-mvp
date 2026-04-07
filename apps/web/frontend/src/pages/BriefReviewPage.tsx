import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone, SectionNavigator, CheckpointBlock } from '../components/shared';

const SECTIONS = [
  { id: 'background', label: 'Background', status: 'complete' },
  { id: 'methodology', label: 'Research Methodology', status: 'complete' },
  { id: 'audience', label: 'Target Audience', status: 'needs_review' },
  { id: 'objectives', label: 'Research Objectives', status: 'complete' },
  { id: 'criteria', label: 'Success Criteria', status: 'pending' },
];

export function BriefReviewPage() {
  const { projectId } = useParams();
  const [activeSection, setActiveSection] = useState('background');
  const [content, setContent] = useState(
    'The client is a mid-market CPG brand looking to understand shifting consumer attitudes in the premium wellness segment...',
  );

  return (
    <AppShell
      currentStage={2}
      projectId={projectId}
      chips={[
        { label: 'Stage', value: 'Brief Review' },
        { label: 'Project', value: projectId || '' },
      ]}
      actions={['Tighten language', 'Remove ambiguity', 'Shorten for executive']}
    >
      <PageHeader title="Research Brief" subtitle="Step 2 of 6 — Upload and review your research brief" />
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Upload Brief</h3>
        <FileDropzone accept=".docx,.pdf,.md" label="Drop research brief here (.docx, .pdf, .md)" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 14 }}>
        <SectionNavigator sections={SECTIONS} activeId={activeSection} onSelect={setActiveSection} />
        <div className="card">
          <h3 style={{ textTransform: 'capitalize' }}>{activeSection.replace('_', ' ')}</h3>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={8}
            style={{ width: '100%', padding: 12, border: '1px solid var(--line)', borderRadius: 10, marginTop: 8, fontFamily: 'inherit', fontSize: 14 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button className="btn btn-secondary btn-sm">Tighten language</button>
            <button className="btn btn-secondary btn-sm">Remove ambiguity</button>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <CheckpointBlock
          title="Finalize Brief"
          description="Lock the brief to proceed to survey building."
          status="ready"
        />
      </div>
    </AppShell>
  );
}
