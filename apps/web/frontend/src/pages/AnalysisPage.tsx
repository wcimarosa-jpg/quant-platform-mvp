import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, StatusBadge, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import type { QAReport } from '../api/types';

export function AnalysisPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get('run_id') || '';

  const [qaReport, setQaReport] = useState<QAReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  async function handleRunQA() {
    if (!runId) {
      setError('No run_id provided. Generate tables first from the Mapping page.');
      return;
    }
    setRunning(true);
    setError('');
    try {
      const report = await api.runQA(runId);
      setQaReport(report);
    } catch {
      setError('QA run failed. Verify the run exists.');
    } finally {
      setRunning(false);
    }
  }

  function handleApprove() {
    navigate(`/projects/${projectId}/report?run_id=${runId}`);
  }

  return (
    <AppShell
      currentStage={5}
      projectId={projectId}
      chips={[
        { label: 'Stage', value: 'Analysis' },
        { label: 'Project', value: projectId || '' },
        { label: 'Run', value: runId || 'none' },
      ]}
      actions={['Create custom cut', 'Explain QA finding', 'Manual analysis']}
    >
      <PageHeader title="Analysis" subtitle="Step 5 of 6 — Run QA and review results" />

      {error && <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}><span style={{ color: 'var(--warn)' }}>{error}</span></div>}

      {!runId && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>No analysis run available</h3>
          <p style={{ fontSize: 14, color: 'var(--muted)' }}>
            Generate tables from the Mapping page first. The mapping page will redirect here with a run_id once tables are generated.
          </p>
          <button className="btn btn-secondary" style={{ marginTop: 10 }} onClick={() => navigate(`/projects/${projectId}/mapping`)}>
            ← Back to Mapping
          </button>
        </div>
      )}

      {runId && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Run {runId}</h3>
          <button className="btn btn-primary" onClick={handleRunQA} disabled={running}>
            {running ? 'Running QA...' : 'Run QA Checks'}
          </button>
        </div>
      )}

      {qaReport && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>QA Report</h3>
            <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
              <StatusBadge status={qaReport.passed ? 'PASSED' : 'ISSUES'} variant={qaReport.passed ? 'ok' : 'warn'} />
              <span style={{ fontSize: 14 }}>
                {qaReport.error_count} error(s), {qaReport.warning_count} warning(s)
              </span>
            </div>
            {qaReport.findings.length > 0 && (
              <table style={{ marginTop: 12 }}>
                <thead><tr><th>Severity</th><th>Table</th><th>Finding</th></tr></thead>
                <tbody>
                  {qaReport.findings.slice(0, 10).map((f) => (
                    <tr key={f.finding_id}>
                      <td><StatusBadge status={f.severity} variant={f.severity === 'error' ? 'warn' : 'info'} /></td>
                      <td>{f.table_id}</td>
                      <td style={{ fontSize: 13 }}>{f.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <CheckpointBlock
            title="Continue to Reporting"
            description={qaReport.passed ? 'QA passed — ready to report.' : 'Review findings before continuing.'}
            status="ready"
            onApprove={handleApprove}
          />
        </>
      )}
    </AppShell>
  );
}
