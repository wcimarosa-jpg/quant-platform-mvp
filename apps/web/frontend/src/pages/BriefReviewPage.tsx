import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import type { Brief, BriefAnalysis } from '../api/types';

type EditableField = 'objectives' | 'audience' | 'category' | 'geography' | 'constraints';

const FIELD_LABELS: Record<EditableField, string> = {
  objectives: 'Objectives',
  audience: 'Audience',
  category: 'Category',
  geography: 'Geography',
  constraints: 'Constraints',
};

const EDITABLE_FIELDS: EditableField[] = ['objectives', 'audience', 'category', 'geography', 'constraints'];

function getBriefField(brief: Brief, field: EditableField): string {
  return (brief[field] as string) || '';
}

export function BriefReviewPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const briefIdFromUrl = searchParams.get('brief_id') || '';

  const [briefId, setBriefId] = useState<string>(briefIdFromUrl);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [activeField, setActiveField] = useState<EditableField>('objectives');
  const [editValue, setEditValue] = useState<string>('');
  const [analysis, setAnalysis] = useState<BriefAnalysis | null>(null);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');

  // Track the field that was active when the brief was last loaded so we
  // don't accidentally overwrite editValue when activeField changes after
  // an unrelated brief refresh.
  const initialFieldRef = useRef<EditableField>('objectives');

  // Load brief if briefId is set
  useEffect(() => {
    if (!briefId) return;
    let cancelled = false;
    initialFieldRef.current = activeField;
    api.getBrief(briefId)
      .then((b) => {
        if (cancelled) return;
        setBrief(b);
        setEditValue(getBriefField(b, initialFieldRef.current));
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load brief.');
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [briefId]);

  // Sync edit value when field changes (only if no unsaved edits)
  useEffect(() => {
    if (brief) {
      setEditValue(getBriefField(brief, activeField));
    }
  }, [activeField, brief]);

  function isDirty(): boolean {
    if (!brief) return false;
    return editValue !== getBriefField(brief, activeField);
  }

  function handleFieldSwitch(field: EditableField) {
    if (field === activeField) return;
    if (isDirty()) {
      const ok = window.confirm('You have unsaved changes. Discard them?');
      if (!ok) return;
    }
    setActiveField(field);
  }

  async function handleUpload(file: File) {
    if (!projectId) return;
    setUploading(true);
    setError('');
    try {
      const result = await api.uploadBrief(projectId, file);
      setBriefId(result.brief_id);
      setSearchParams({ brief_id: result.brief_id });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setError(`Upload failed: ${msg.slice(0, 200)}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveField() {
    if (!brief) return;
    setSaving(true);
    setError('');
    try {
      const updated = await api.updateBrief(brief.brief_id, { [activeField]: editValue });
      setBrief(updated);
      setEditValue(getBriefField(updated, activeField));
    } catch {
      setError('Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }

  async function handleAnalyze() {
    if (!brief) return;
    setAnalyzing(true);
    setError('');
    try {
      const result = await api.analyzeBrief(brief.brief_id);
      setAnalysis(result);
      // Re-fetch the brief so the checkpoint reflects any updates
      // (e.g., assumptions applied during analysis flow).
      const refreshed = await api.getBrief(brief.brief_id);
      setBrief(refreshed);
    } catch {
      setError('Failed to analyze brief.');
    } finally {
      setAnalyzing(false);
    }
  }

  function handleApprove() {
    navigate(`/projects/${projectId}/survey`);
  }

  // Determine if checkpoint is ready: brief is complete OR analyzer
  // produced a result with all assumptions resolved.
  const checkpointReady = brief
    ? brief.is_complete || (analysis !== null && analysis.all_resolved)
    : false;
  const checkpointDescription = brief
    ? brief.is_complete
      ? 'All required fields complete.'
      : analysis !== null && analysis.all_resolved
        ? 'Analyzer resolved all assumptions. Ready to continue.'
        : `Missing: ${brief.missing_fields.join(', ')}. Run analyzer to suggest fixes.`
    : '';

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

      {!brief && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Upload Brief</h3>
          {uploading ? (
            <p style={{ color: 'var(--muted)' }}>Uploading and parsing...</p>
          ) : (
            <FileDropzone accept=".docx,.pdf,.md" label="Drop research brief here (.docx, .pdf, .md)" onFile={handleUpload} />
          )}
        </div>
      )}

      {error && <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}><span style={{ color: 'var(--warn)' }}>{error}</span></div>}

      {brief && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 14 }}>
            <div className="section-nav">
              {EDITABLE_FIELDS.map((field) => {
                const value = getBriefField(brief, field);
                const isComplete = value !== '';
                return (
                  <button
                    key={field}
                    className={`section-nav-item ${field === activeField ? 'active' : ''}`}
                    onClick={() => handleFieldSwitch(field)}
                    disabled={saving}
                  >
                    {FIELD_LABELS[field]}
                    <span className={`badge badge-${isComplete ? 'ok' : 'warn'}`}>{isComplete ? '✓' : '!'}</span>
                  </button>
                );
              })}
            </div>
            <div className="card">
              <h3>{FIELD_LABELS[activeField]}</h3>
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                rows={8}
                disabled={saving}
                style={{ width: '100%', padding: 12, border: '1px solid var(--line)', borderRadius: 10, marginTop: 8, fontFamily: 'inherit', fontSize: 14, background: '#fffdfa' }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
                <button className="btn btn-primary btn-sm" onClick={handleSaveField} disabled={saving || !isDirty()}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
                {isDirty() && !saving && <span style={{ fontSize: 12, color: 'var(--muted)' }}>Unsaved changes</span>}
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Brief Analysis</h3>
              <button className="btn btn-secondary btn-sm" onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? 'Analyzing...' : 'Run Analyzer'}
              </button>
            </div>
            {analysis && (
              <div style={{ marginTop: 10 }}>
                <p style={{ fontSize: 14, marginBottom: 8 }}><strong>Summary:</strong> {analysis.summary}</p>
                {analysis.gaps.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <strong style={{ fontSize: 14 }}>Gaps:</strong>
                    <ul style={{ marginLeft: 20, fontSize: 14 }}>
                      {analysis.gaps.map((g, i) => <li key={i}>{g}</li>)}
                    </ul>
                  </div>
                )}
                {analysis.assumptions.length > 0 && (
                  <div>
                    <strong style={{ fontSize: 14 }}>Suggested Assumptions:</strong>
                    <ul style={{ marginLeft: 20, fontSize: 14 }}>
                      {analysis.assumptions.map((a) => (
                        <li key={a.assumption_id}>
                          <em>{a.field}:</em> {a.proposal}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
                  Status: {analysis.all_resolved ? 'All assumptions resolved' : 'Pending assumptions'}
                </p>
              </div>
            )}
          </div>

          <div style={{ marginTop: 16 }}>
            <CheckpointBlock
              title="Finalize Brief & Continue"
              description={checkpointDescription}
              status={checkpointReady ? 'ready' : 'pending'}
              onApprove={handleApprove}
            />
          </div>
        </>
      )}
    </AppShell>
  );
}
