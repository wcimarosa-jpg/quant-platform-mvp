import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, StatusBadge, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import type { QAReport } from '../api/types';

// Validate the shape of run_id from a query param. Backend uses
// "tblrun-<8 hex chars>" but we accept any reasonable identifier here.
const RUN_ID_PATTERN = /^[a-zA-Z0-9_-]{4,64}$/;

export function AnalysisPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get('run_id') || '';

  const [qaReport, setQaReport] = useState<QAReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  const isValidRunId = runId !== '' && RUN_ID_PATTERN.test(runId);

  async function handleRunQA() {
    if (!runId) {
      setError('No run_id provided. Generate tables first from the Mapping page.');
      return;
    }
    if (!isValidRunId) {
      setError(`Invalid run_id format: ${runId.slice(0, 80)}`);
      return;
    }
    setRunning(true);
    setError('');
    setAttempt((a) => a + 1);
    try {
      const report = await api.runQA(runId);
      setQaReport(report);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(`QA run failed: ${msg.slice(0, 200)}`);
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

      {error && (
        <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}>
          <span style={{ color: 'var(--warn)' }}>{error}</span>
          {attempt > 0 && !running && (
            <div style={{ marginTop: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={handleRunQA}>
                Retry
              </button>
            </div>
          )}
        </div>
      )}

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

      {runId && !isValidRunId && (
        <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}>
          <h3>Invalid run_id</h3>
          <p style={{ fontSize: 14, color: 'var(--muted)' }}>
            The run_id in the URL ({runId.slice(0, 80)}) does not match the expected format.
            Generate a fresh run from the Mapping page.
          </p>
          <button className="btn btn-secondary" style={{ marginTop: 10 }} onClick={() => navigate(`/projects/${projectId}/mapping`)}>
            ← Back to Mapping
          </button>
        </div>
      )}

      {isValidRunId && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Run {runId}</h3>
          <button className="btn btn-primary" onClick={handleRunQA} disabled={running}>
            {running ? 'Running QA...' : qaReport ? 'Re-run QA' : 'Run QA Checks'}
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
