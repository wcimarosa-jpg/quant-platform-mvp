import { useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, KPICard, CheckpointBlock } from '../components/shared';

export function ReportingPage() {
  const { projectId } = useParams();

  return (
    <AppShell currentStage={6} projectId={projectId}>
      <PageHeader title="Strategic Summary & Export" subtitle="Step 6 of 6 — Generate report and export deliverables" />
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Strategic Summary Draft</h3>
        <div style={{ padding: 12, background: '#fffdfa', borderRadius: 10, border: '1px solid var(--line)', marginTop: 8 }}>
          <p><strong>Headline:</strong> Four distinct consumer segments emerge, with Premium Explorers representing the highest-value growth opportunity.</p>
          <p style={{ marginTop: 8 }}><strong>Implication:</strong> Innovation-led messaging will resonate most with the 28% Premium Explorer segment, who show 72% purchase intent.</p>
          <p style={{ marginTop: 8 }}><strong>Recommendation:</strong> Prioritize new product development targeting Premium Explorers. Secondary focus on converting Value Seekers through targeted pricing strategies.</p>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button className="btn btn-secondary btn-sm">Tighten executive tone</button>
          <button className="btn btn-secondary btn-sm">Add evidence footnotes</button>
        </div>
      </div>
      <div className="cards">
        <KPICard label="Project Cost" value="$427" />
        <KPICard label="Total Portfolio" value="$2,148" />
        <KPICard label="Tokens Used" value="142K" />
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Export Manager</h3>
        <table>
          <thead><tr><th>Artifact</th><th>Format</th><th></th></tr></thead>
          <tbody>
            <tr><td>Strategic Summary</td><td>DOCX</td><td><button className="btn btn-secondary btn-sm">Export</button></td></tr>
            <tr><td>Questionnaire</td><td>Decipher XML</td><td><button className="btn btn-secondary btn-sm">Export</button></td></tr>
            <tr><td>Data Tables</td><td>Excel</td><td><button className="btn btn-secondary btn-sm">Export</button></td></tr>
            <tr><td>Segment Profiles</td><td>CSV</td><td><button className="btn btn-secondary btn-sm">Export</button></td></tr>
          </tbody>
        </table>
      </div>
      <CheckpointBlock title="Confirm Export" description="Verify provenance and sharing intent before export." status="ready" />
    </AppShell>
  );
}
