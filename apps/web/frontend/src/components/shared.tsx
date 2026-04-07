import type { ReactNode } from 'react';
import { useCallback } from 'react';

// -- KPI Card --
export function KPICard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

// -- Status Badge --
type BadgeVariant = 'ok' | 'warn' | 'info' | 'running';
export function StatusBadge({ status, variant = 'info' }: { status: string; variant?: BadgeVariant }) {
  return <span className={`badge badge-${variant}`}>{status}</span>;
}

// -- File Dropzone --
interface FileDropzoneProps {
  accept?: string;
  label?: string;
  onFile?: (file: File) => void;
}

export function FileDropzone({ accept = '.docx,.pdf', label, onFile }: FileDropzoneProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && onFile) onFile(file);
    },
    [onFile],
  );

  return (
    <label className="dropzone">
      <input type="file" accept={accept} onChange={handleChange} hidden />
      <div className="dropzone-content">
        <span className="dropzone-icon">+</span>
        <span>{label || `Drop file here or click to browse (${accept})`}</span>
      </div>
    </label>
  );
}

// -- Checkpoint Block --
interface CheckpointProps {
  title: string;
  description?: string;
  status?: 'ready' | 'locked' | 'pending';
  onApprove?: () => void;
}

export function CheckpointBlock({ title, description, status = 'pending', onApprove }: CheckpointProps) {
  return (
    <div className="card checkpoint">
      <h3>{title}</h3>
      {description && <p style={{ color: 'var(--muted)', fontSize: 14 }}>{description}</p>}
      <div style={{ marginTop: 10 }}>
        {status === 'ready' && (
          <button className="btn btn-primary" onClick={onApprove}>Approve</button>
        )}
        {status === 'locked' && <StatusBadge status="Locked" variant="ok" />}
        {status === 'pending' && <StatusBadge status="Pending" variant="warn" />}
      </div>
    </div>
  );
}

// -- Section Navigator --
interface Section {
  id: string;
  label: string;
  status?: string;
}

interface SectionNavProps {
  sections: Section[];
  activeId: string;
  onSelect: (id: string) => void;
}

export function SectionNavigator({ sections, activeId, onSelect }: SectionNavProps) {
  return (
    <div className="section-nav">
      {sections.map((s) => (
        <button
          key={s.id}
          className={`section-nav-item ${s.id === activeId ? 'active' : ''}`}
          onClick={() => onSelect(s.id)}
        >
          {s.label}
          {s.status && <StatusBadge status={s.status} variant={s.status === 'complete' ? 'ok' : 'warn'} />}
        </button>
      ))}
    </div>
  );
}

// -- Page Header --
export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="topbar">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
