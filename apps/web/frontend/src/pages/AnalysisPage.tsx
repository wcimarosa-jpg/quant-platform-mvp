import { useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, StatusBadge } from '../components/shared';

const RUNS = [
  { id: 'run-18', type: 'segmentation', status: 'completed' },
  { id: 'run-19', type: 'drivers', status: 'queued' },
  { id: 'run-20', type: 'segmentation', status: 'failed' },
];

const SEGMENTS = [
  { name: 'Premium Explorers', size: '28%', topDriver: 'Innovation', purchaseIntent: '72%' },
  { name: 'Value Seekers', size: '35%', topDriver: 'Price', purchaseIntent: '45%' },
  { name: 'Loyalists', size: '22%', topDriver: 'Trust', purchaseIntent: '68%' },
  { name: 'Newcomers', size: '15%', topDriver: 'Curiosity', purchaseIntent: '55%' },
];

export function AnalysisPage() {
  const { projectId } = useParams();

  return (
    <AppShell currentStage={5} projectId={projectId}>
      <PageHeader title="Analysis" subtitle="Step 5 of 6 — Run analysis and review results" />
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Run Queue</h3>
        <table>
          <thead>
            <tr><th>Run ID</th><th>Type</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {RUNS.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.type}</td>
                <td>
                  <StatusBadge
                    status={r.status}
                    variant={r.status === 'completed' ? 'ok' : r.status === 'failed' ? 'warn' : 'running'}
                  />
                </td>
                <td>
                  {r.status === 'failed' && <button className="btn btn-secondary btn-sm">Re-run</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>KMeans Segment Snapshot</h3>
        <table>
          <thead>
            <tr><th>Segment</th><th>Size</th><th>Top Driver</th><th>Purchase Intent</th></tr>
          </thead>
          <tbody>
            {SEGMENTS.map((s) => (
              <tr key={s.name}>
                <td><strong>{s.name}</strong></td>
                <td>{s.size}</td>
                <td>{s.topDriver}</td>
                <td>{s.purchaseIntent}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>AI Insight</h3>
        <p style={{ fontSize: 14 }}>
          Premium Explorers over-index on innovation (+12pt vs. total sample).
          This segment shows the highest purchase intent and responds strongly to
          new product messaging.
        </p>
      </div>
    </AppShell>
  );
}
