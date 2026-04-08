import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone, StatusBadge, CheckpointBlock } from '../components/shared';
import api from '../api/client';

interface ParsedData {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
}

function parseCSV(text: string): ParsedData {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) {
    return { columns: [], rows: [], rowCount: 0 };
  }
  const columns = lines[0].split(',').map((c) => c.trim());
  const rows = lines.slice(1).map((line) => {
    const cells = line.split(',');
    const row: Record<string, unknown> = {};
    columns.forEach((col, i) => {
      const cell = cells[i]?.trim() || '';
      const num = Number(cell);
      row[col] = isNaN(num) || cell === '' ? cell : num;
    });
    return row;
  });
  return { columns, rows, rowCount: rows.length };
}

export function MappingPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [parsed, setParsed] = useState<ParsedData | null>(null);
  const [filename, setFilename] = useState('');
  const [generating, setGenerating] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function handleFile(file: File) {
    setFilename(file.name);
    setError('');
    try {
      const text = await file.text();
      const data = parseCSV(text);
      if (data.columns.length === 0) {
        setError('CSV file appears empty or malformed.');
        return;
      }
      setParsed(data);
    } catch {
      setError('Failed to parse file. Use a CSV with header row.');
    }
  }

  async function handleGenerate() {
    if (!parsed || !projectId) return;
    setGenerating(true);
    setError('');
    try {
      // Build a minimal variable spec from columns
      const variables = parsed.columns.map((col) => ({
        var_name: col,
        var_label: col,
        var_type: 'single',
        value_labels: {},
      }));
      const result = await api.generateTables({
        project_id: projectId,
        mapping_id: 'auto',
        mapping_version: 1,
        questionnaire_version: 1,
        variables,
        data_rows: parsed.rows,
      });
      setRunId(result.run_id);
    } catch (err) {
      setError('Table generation failed. Check that all columns have numeric values.');
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

      {error && <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}><span style={{ color: 'var(--warn)' }}>{error}</span></div>}

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
            </tbody>
          </table>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
            Columns: {parsed.columns.slice(0, 8).join(', ')}{parsed.columns.length > 8 ? '…' : ''}
          </p>
        </div>
      )}

      {parsed && !runId && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Auto-Map Columns</h3>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
            All columns will be treated as single-select variables. Advanced mapping coming in P12-04.
          </p>
          <table>
            <thead>
              <tr><th>Column</th><th>Type</th><th>Confidence</th></tr>
            </thead>
            <tbody>
              {parsed.columns.slice(0, 10).map((col) => (
                <tr key={col}>
                  <td>{col}</td>
                  <td>single</td>
                  <td><StatusBadge status="auto" variant="ok" /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={handleGenerate} disabled={generating}>
            {generating ? 'Generating tables...' : 'Generate Tables'}
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
