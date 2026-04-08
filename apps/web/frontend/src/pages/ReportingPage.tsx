import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, KPICard, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import type { CostResponse } from '../api/types';

export function ReportingPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get('run_id') || '';

  const [cost, setCost] = useState<CostResponse>({ total_cost_usd: 0, total_tokens: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.getCost()
      .then((c) => { if (!cancelled) setCost(c); })
      .catch(() => { if (!cancelled) setCost({ total_cost_usd: 0, total_tokens: 0 }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <AppShell
      currentStage={6}
      projectId={projectId}
      chips={[
        { label: 'Stage', value: 'Reporting' },
        { label: 'Project', value: projectId || '' },
        { label: 'Run', value: runId || 'none' },
      ]}
      actions={['Tighten executive tone', 'Add evidence footnotes', 'Manual edit']}
    >
      <PageHeader title="Strategic Summary & Export" subtitle="Step 6 of 6 — Generate report and export deliverables" />

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Strategic Summary Draft</h3>
        <div style={{ padding: 12, background: '#fffdfa', borderRadius: 10, border: '1px solid var(--line)', marginTop: 8, fontSize: 14 }}>
          <p><strong>Headline:</strong> Project {projectId} analysis complete with run {runId || '(none)'}.</p>
          <p style={{ marginTop: 8 }}><strong>Implication:</strong> Tables generated and QA-checked. Strategic interpretation requires P12-04 LLM integration.</p>
          <p style={{ marginTop: 8 }}><strong>Recommendation:</strong> Review the QA findings from the previous step, then export the deliverables below.</p>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button className="btn btn-secondary btn-sm" disabled>Tighten executive tone (P12-04)</button>
          <button className="btn btn-secondary btn-sm" disabled>Add evidence footnotes (P12-04)</button>
        </div>
      </div>

      <div className="cards">
        <KPICard
          label="Total Cost"
          value={loading ? '—' : `$${cost.total_cost_usd.toFixed(2)}`}
        />
        <KPICard
          label="Total Tokens"
          value={loading ? '—' : cost.total_tokens.toLocaleString()}
        />
        <KPICard
          label="Cost Sources Tracked"
          value={loading ? '—' : Object.keys(cost.by_stage || {}).length}
        />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Export Manager</h3>
        <table>
          <thead><tr><th>Artifact</th><th>Format</th><th></th></tr></thead>
          <tbody>
            <tr><td>Strategic Summary</td><td>DOCX</td><td><button className="btn btn-secondary btn-sm" disabled>Export (P12-04)</button></td></tr>
            <tr><td>Questionnaire</td><td>Decipher XML</td><td><button className="btn btn-secondary btn-sm" disabled>Export (P12-04)</button></td></tr>
            <tr><td>Data Tables</td><td>Excel</td><td><button className="btn btn-secondary btn-sm" disabled>Export (P12-04)</button></td></tr>
            <tr><td>Segment Profiles</td><td>CSV</td><td><button className="btn btn-secondary btn-sm" disabled>Export (P12-04)</button></td></tr>
          </tbody>
        </table>
      </div>

      <CheckpointBlock title="Confirm Export" description="Verify provenance and sharing intent before export." status="pending" />
    </AppShell>
  );
}
