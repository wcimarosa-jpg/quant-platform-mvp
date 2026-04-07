import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { PageHeader, FileDropzone } from '../components/shared';
import api from '../api/client';

export function ProjectSetupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [methodology, setMethodology] = useState('segmentation');
  const [saving, setSaving] = useState(false);

  async function handleCreate() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const result = await api.createProject({ name, methodology });
      const projectId = (result as { id?: string }).id || 'new';
      navigate(`/projects/${projectId}/brief`);
    } catch {
      alert('Failed to create project. Is the API server running?');
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
              <option value="segmentation">Segmentation</option>
              <option value="drivers">Drivers</option>
              <option value="maxdiff">MaxDiff</option>
              <option value="au">A&U</option>
              <option value="brand_tracker">Brand Tracker</option>
              <option value="concept_test">Concept Test</option>
            </select>
          </label>
        </div>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>SOW Upload (Optional)</h3>
        <FileDropzone accept=".docx,.pdf" label="Drop SOW file here (.docx or .pdf)" />
      </div>
      <button className="btn btn-primary" onClick={handleCreate} disabled={saving || !name.trim()}>
        {saving ? 'Creating...' : 'Create Project & Continue'}
      </button>
    </AppShell>
  );
}
