import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone, StatusBadge, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import { parseCSV, type ParsedCSV } from '../lib/csv';
import { profileColumn, pickTableTypes, type ColumnProfile, type ColumnKind } from '../lib/profile';

const MAX_ROWS = 50_000;

function badgeVariant(kind: ColumnKind): 'ok' | 'warn' | 'info' {
  if (kind === 'categorical') return 'ok';
  if (kind === 'continuous') return 'info';
  return 'warn';
}

export function MappingPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [parsed, setParsed] = useState<ParsedCSV | null>(null);
  const [filename, setFilename] = useState('');
  const [generating, setGenerating] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState('');

  // Profile columns whenever parsed data changes
  const profiles = useMemo<ColumnProfile[]>(() => {
    if (!parsed) return [];
    return parsed.columns.map((c) => profileColumn(c, parsed.rows));
  }, [parsed]);

  const tabulatable = useMemo(
    () => profiles.filter((p) => p.kind === 'categorical' || p.kind === 'continuous'),
    [profiles],
  );
  const skipped = useMemo(
    () => profiles.filter((p) => p.kind === 'text' || p.kind === 'empty'),
    [profiles],
  );

  async function handleFile(file: File) {
    setFilename(file.name);
    setError('');
    setRunId(null);
    setParsed(null);
    try {
      const text = await file.text();
      const data = parseCSV(text);
      if (data.columns.length === 0) {
        setError('CSV file appears empty or malformed.');
        return;
      }
      if (data.rowCount > MAX_ROWS) {
        setError(`File has ${data.rowCount.toLocaleString()} rows. MVP limit is ${MAX_ROWS.toLocaleString()}.`);
        return;
      }
      setParsed(data);
    } catch {
      setError('Failed to parse file. Use a CSV with header row.');
    }
  }

  async function handleGenerate() {
    if (!parsed || !projectId) return;
    if (tabulatable.length === 0) {
      setError('No numeric columns found. Table generation requires numeric-coded data.');
      return;
    }
    setGenerating(true);
    setError('');
    try {
      // Build variable specs from profiled columns. var_name is required;
      // value_labels is optional but populated for categorical columns.
      const variables = tabulatable.map((p) => ({
        var_name: p.name,
        question_id: p.name,
        question_text: p.name,
        value_labels: p.valueLabels,
      }));

      const tableTypes = pickTableTypes(tabulatable);

      const result = await api.generateTables({
        project_id: projectId,
        mapping_id: 'auto',
        mapping_version: 1,
        questionnaire_version: 1,
        variables,
        data_rows: parsed.rows,
        config: {
          table_types: tableTypes,
          banner_variables: [],
          significance: { enabled: true, confidence_level: 0.95, method: 'chi_square' },
          base_size_minimum: 30,
        },
      });
      setRunId(result.run_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Table generation failed.';
      setError(`Table generation failed: ${message.slice(0, 200)}`);
    } finally {
      setGenerating(false);
    }
  }

  function handleContinue() {
    if (runId) {
      navigate(`/projects/${projectId}/analysis?run_id=${runId}`);
    }
  }

  return (
    <AppShell
      currentStage={4}
      projectId={projectId}
      chips={[
        { label: 'Stage', value: 'Data Mapping' },
        { label: 'Project', value: projectId || '' },
      ]}
      actions={['Auto-map columns', 'Fix low-confidence', 'Show rationale']}
    >
      <PageHeader title="Data Mapping" subtitle="Step 4 of 6 — Upload data and generate tables" />

      {error && (
        <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}>
          <span style={{ color: 'var(--warn)' }}>{error}</span>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Upload Data File</h3>
        <FileDropzone accept=".csv" label="Drop CSV file here (CSV only for MVP)" onFile={handleFile} />
        {filename && <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>Loaded: {filename}</p>}
      </div>

      {parsed && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Data Profile</h3>
          <table>
            <thead>
              <tr><th>Field</th><th>Value</th></tr>
            </thead>
            <tbody>
              <tr><td>Filename</td><td>{filename}</td></tr>
              <tr><td>Rows</td><td>{parsed.rowCount.toLocaleString()}</td></tr>
              <tr><td>Columns</td><td>{parsed.columns.length}</td></tr>
              <tr><td>Tabulatable</td><td>{tabulatable.length}</td></tr>
              <tr><td>Skipped</td><td>{skipped.length} (text or empty)</td></tr>
            </tbody>
          </table>
        </div>
      )}

      {parsed && !runId && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Column Profile</h3>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
            {tabulatable.length} of {profiles.length} columns will be tabulated.
            {skipped.length > 0 && ` ${skipped.length} text/empty columns skipped.`}
          </p>
          <table>
            <thead>
              <tr><th>Column</th><th>Kind</th><th>Unique Values</th><th>Status</th></tr>
            </thead>
            <tbody>
              {profiles.slice(0, 30).map((p) => (
                <tr key={p.name}>
                  <td>{p.name}</td>
                  <td>{p.kind}</td>
                  <td>{p.uniqueCount}</td>
                  <td>
                    <StatusBadge
                      status={p.kind === 'text' || p.kind === 'empty' ? 'skipped' : 'tabulatable'}
                      variant={badgeVariant(p.kind)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {profiles.length > 30 && (
            <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
              Showing first 30 of {profiles.length} columns.
            </p>
          )}
          <button
            className="btn btn-primary"
            style={{ marginTop: 12 }}
            onClick={handleGenerate}
            disabled={generating || tabulatable.length === 0}
          >
            {generating ? 'Generating tables...' : `Generate Tables (${tabulatable.length} cols)`}
          </button>
        </div>
      )}

      {runId && (
        <CheckpointBlock
          title={`Tables generated (run: ${runId})`}
          description="Mapping locked. Continue to analysis."
          status="ready"
          onApprove={handleContinue}
        />
      )}
    </AppShell>
  );
}
