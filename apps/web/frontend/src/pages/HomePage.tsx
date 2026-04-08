import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { KPICard, PageHeader, StatusBadge } from '../components/shared';
import api from '../api/client';
import type { Project, CostResponse } from '../api/types';

export function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [cost, setCost] = useState<CostResponse>({ total_cost_usd: 0, total_tokens: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [projResp, costResp] = await Promise.all([
          api.listProjects(),
          api.getCost().catch(() => ({ total_cost_usd: 0, total_tokens: 0 } as CostResponse)),
        ]);
        if (cancelled) return;
        setProjects(projResp.projects || []);
        setCost(costResp);
      } catch (err) {
        if (cancelled) return;
        setError('Failed to load projects. Check your connection.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell currentStage={0}>
      <PageHeader
        title="Home"
        subtitle="Resume work, monitor project health, track costs"
        action={<Link to="/projects/new" className="btn btn-primary">+ Create Project</Link>}
      />
      <div className="cards">
        <KPICard label="Active Projects" value={projects.length} />
        <KPICard label="Total Tokens" value={cost.total_tokens.toLocaleString()} />
        <KPICard label="Total Cost" value={`$${cost.total_cost_usd.toFixed(2)}`} />
      </div>
      {loading && <p style={{ color: 'var(--muted)' }}>Loading projects...</p>}
      {error && <p style={{ color: 'var(--warn)' }}>{error}</p>}
      {!loading && !error && (
        <table>
          <thead>
            <tr><th>Project</th><th>Methodology</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.methodology}</td>
                <td><StatusBadge status={p.status} variant={p.status === 'active' ? 'ok' : 'info'} /></td>
                <td><Link to={`/projects/${p.id}/brief`} className="btn btn-secondary btn-sm">Open</Link></td>
              </tr>
            ))}
            {projects.length === 0 && <tr><td colSpan={4} style={{ color: 'var(--muted)' }}>No projects yet. Create one to get started.</td></tr>}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}
