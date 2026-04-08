import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone } from '../components/shared';
import api from '../api/client';
import type { Methodology } from '../api/types';

// Fallback list when the API is unreachable on first load.
const FALLBACK_METHODOLOGIES: Methodology[] = [
  { value: 'segmentation', label: 'Segmentation', description: '' },
  { value: 'drivers', label: 'Drivers', description: '' },
  { value: 'maxdiff', label: 'MaxDiff', description: '' },
];

export function ProjectSetupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [methodologies, setMethodologies] = useState<Methodology[]>([]);
  const [methodology, setMethodology] = useState('segmentation');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Load methodologies from the backend so this list stays in sync with
  // the survey builder. Falls back to a small hardcoded list on failure.
  useEffect(() => {
    let cancelled = false;
    api.listMethodologies()
      .then((r) => {
        if (cancelled) return;
        const list = r.methodologies || [];
        if (list.length > 0) {
          setMethodologies(list);
          if (!list.find((m) => m.value === methodology)) {
            setMethodology(list[0].value);
          }
        } else {
          setMethodologies(FALLBACK_METHODOLOGIES);
        }
      })
      .catch(() => {
        if (!cancelled) setMethodologies(FALLBACK_METHODOLOGIES);
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate() {
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const project = await api.createProject({ name, methodology });
      // If a SOW file was selected, upload it to the new project before
      // navigating. The upload result is the brief_id we pass on so the
      // BriefReviewPage can load directly into editing mode.
      if (pendingFile) {
        try {
          const upload = await api.uploadBrief(project.id, pendingFile);
          navigate(`/projects/${project.id}/brief?brief_id=${upload.brief_id}`);
          return;
        } catch (uploadErr) {
          // Project created, but SOW upload failed. Continue without it.
          const msg = uploadErr instanceof Error ? uploadErr.message : 'unknown';
          setError(`Project created, but SOW upload failed: ${msg.slice(0, 200)}. Continuing to brief review.`);
        }
      }
      navigate(`/projects/${project.id}/brief`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Check your connection and try again.';
      setError(`Failed to create project: ${msg.slice(0, 200)}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell currentStage={1}>
      <PageHeader title="Project Setup" subtitle="Step 1 of 6 — Create your research project" />
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Project Metadata</h3>
        <div style={{ display: 'grid', gap: 12, marginTop: 10 }}>
          <label>
            <span style={{ fontSize: 14, color: 'var(--muted)' }}>Project Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Q4 Brand Health Study"
              style={{ display: 'block', width: '100%', padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 10, marginTop: 4 }}
            />
          </label>
          <label>
            <span style={{ fontSize: 14, color: 'var(--muted)' }}>Methodology</span>
            <select
              value={methodology}
              onChange={(e) => setMethodology(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 10, marginTop: 4 }}
            >
              {methodologies.map((m) => (
                <option key={m.value} value={m.value}>{m.label || m.value}</option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>SOW Upload (Optional)</h3>
        <FileDropzone
          accept=".docx,.pdf,.md"
          label={pendingFile ? `Selected: ${pendingFile.name}` : 'Drop SOW file here (.docx, .pdf, .md)'}
          onFile={(file) => setPendingFile(file)}
        />
        {pendingFile && (
          <button
            className="btn btn-secondary btn-sm"
            style={{ marginTop: 8 }}
            onClick={() => setPendingFile(null)}
          >
            Clear file
          </button>
        )}
      </div>
      {error && <div style={{ color: 'var(--warn)', marginBottom: 12, fontSize: 14 }}>{error}</div>}
      <button className="btn btn-primary" onClick={handleCreate} disabled={saving || !name.trim()}>
        {saving ? 'Creating...' : 'Create Project & Continue'}
      </button>
    </AppShell>
  );
}
