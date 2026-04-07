import { useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone, StatusBadge, CheckpointBlock } from '../components/shared';

const MAPPINGS = [
  { question: 'Q1_BRAND_AWARE', column: 'brand_awareness', confidence: 0.95 },
  { question: 'Q2_PURCHASE', column: 'purchase_intent', confidence: 0.88 },
  { question: 'Q3_SATIS', column: 'satisfaction_01', confidence: 0.72 },
  { question: 'Q4_NPS', column: 'nps_score', confidence: 0.97 },
];

export function MappingPage() {
  const { projectId } = useParams();

  return (
    <AppShell currentStage={4} projectId={projectId}>
      <PageHeader title="Data Mapping" subtitle="Step 4 of 6 — Upload data and map variables to questions" />
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Upload Data File</h3>
        <FileDropzone accept=".csv,.xlsx,.sav" label="Drop data file here (.csv, .xlsx, .sav)" />
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Auto-Map Suggestions</h3>
        <table>
          <thead>
            <tr><th>Question Variable</th><th>Data Column</th><th>Confidence</th><th>Action</th></tr>
          </thead>
          <tbody>
            {MAPPINGS.map((m) => (
              <tr key={m.question}>
                <td>{m.question}</td>
                <td>{m.column}</td>
                <td>
                  <StatusBadge
                    status={`${(m.confidence * 100).toFixed(0)}%`}
                    variant={m.confidence >= 0.8 ? 'ok' : 'warn'}
                  />
                </td>
                <td>
                  <button className="btn btn-secondary btn-sm">Accept</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CheckpointBlock title="Lock Mapping" description="Required before running analysis." status="ready" />
    </AppShell>
  );
}
