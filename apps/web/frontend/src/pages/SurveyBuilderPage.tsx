import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, CheckpointBlock } from '../components/shared';
import api from '../api/client';
import type { Draft, Methodology } from '../api/types';

export function SurveyBuilderPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const draftIdFromUrl = searchParams.get('draft_id') || '';

  const [draftId, setDraftId] = useState(draftIdFromUrl);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [methodologies, setMethodologies] = useState<Methodology[]>([]);
  const [selectedMethodology, setSelectedMethodology] = useState('segmentation');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load methodology list on mount
  useEffect(() => {
    api.listMethodologies()
      .then((r) => setMethodologies(r.methodologies || []))
      .catch(() => setMethodologies([]));
  }, []);

  // Load draft if draftId set
  useEffect(() => {
    if (!draftId) return;
    let cancelled = false;
    api.getDraft(draftId)
      .then((d) => {
        if (!cancelled) setDraft(d);
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load draft.');
      });
    return () => { cancelled = true; };
  }, [draftId]);

  async function handleCreateDraft() {
    if (!projectId) return;
    setCreating(true);
    setError('');
    try {
      const d = await api.createDraft({ project_id: projectId, methodology: selectedMethodology });
      setDraft(d);
      setDraftId(d.draft_id);
      setSearchParams({ draft_id: d.draft_id });
    } catch {
      setError('Failed to create draft. Try a different methodology.');
    } finally {
      setCreating(false);
    }
  }

  async function toggleSection(sectionType: string) {
    if (!draft) return;
    const current = new Set(draft.selected_sections);
    if (current.has(sectionType)) {
      current.delete(sectionType);
    } else {
      current.add(sectionType);
    }
    setSaving(true);
    try {
      const updated = await api.updateSections(draft.draft_id, {
        selected_sections: Array.from(current),
      });
      setDraft(updated);
    } catch {
      setError('Failed to update sections.');
    } finally {
      setSaving(false);
    }
  }

  function handleApprove() {
    navigate(`/projects/${projectId}/mapping`);
  }

  return (
    <AppShell
      currentStage={3}
      projectId={projectId}
      chips={[
        { label: 'Stage', value: 'Survey Builder' },
        { label: 'Project', value: projectId || '' },
      ]}
      actions={['Rewrite for clarity', 'Align to objective', 'Suggest alternative']}
    >
      <PageHeader title="Survey Builder" subtitle="Step 3 of 6 — Build questionnaire from brief objectives" />

      {error && <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warn)' }}><span style={{ color: 'var(--warn)' }}>{error}</span></div>}

      {!draft && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Create Survey Draft</h3>
          <label style={{ display: 'block', marginTop: 10 }}>
            <span style={{ fontSize: 14, color: 'var(--muted)' }}>Methodology</span>
            <select
              value={selectedMethodology}
              onChange={(e) => setSelectedMethodology(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 10, marginTop: 4 }}
            >
              {methodologies.length > 0
                ? methodologies.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)
                : <option value="segmentation">Segmentation</option>}
            </select>
          </label>
          <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={handleCreateDraft} disabled={creating}>
            {creating ? 'Creating...' : 'Create Draft'}
          </button>
        </div>
      )}

      {draft && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Sections — {draft.methodology}</h3>
            <p style={{ fontSize: 13, color: 'var(--muted)' }}>
              Toggle sections to include in your questionnaire. {saving && '(Saving...)'}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 12 }}>
              {draft.section_options.map((s) => {
                const isSelected = draft.selected_sections.includes(s.section_type);
                return (
                  <button
                    key={s.section_type}
                    className={`section-nav-item ${isSelected ? 'active' : ''}`}
                    onClick={() => toggleSection(s.section_type)}
                    disabled={s.required}
                    style={{ opacity: s.required ? 0.7 : 1 }}
                  >
                    <span>{s.label}</span>
                    <span className={`badge badge-${isSelected ? 'ok' : 'info'}`}>
                      {s.required ? 'required' : isSelected ? '✓' : 'add'}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <CheckpointBlock
            title="Publish Questionnaire & Continue"
            description={`${draft.selected_sections.length} section(s) selected.`}
            status={draft.selected_sections.length > 0 ? 'ready' : 'pending'}
            onApprove={handleApprove}
          />
        </>
      )}
    </AppShell>
  );
}
