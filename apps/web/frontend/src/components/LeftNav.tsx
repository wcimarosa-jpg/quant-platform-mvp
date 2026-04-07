import { Link } from 'react-router-dom';
import './LeftNav.css';

interface Stage {
  label: string;
  path: string;
}

interface LeftNavProps {
  stages: Stage[];
  activeStage: number;
  projectId?: string;
}

export function LeftNav({ stages, activeStage, projectId }: LeftNavProps) {
  function buildPath(stage: Stage, index: number): string {
    if (index === 0) return '/';
    if (index === 1) return '/projects/new';
    if (!projectId) return '';
    return `/projects/${projectId}/${stage.path}`;
  }

  function isDisabled(index: number): boolean {
    return index >= 2 && !projectId;
  }

  return (
    <nav className="left-nav">
      <div className="brand">egg</div>
      <div className="brand-sub">AI Research</div>
      {stages.map((stage, i) => {
        const disabled = isDisabled(i);
        const path = buildPath(stage, i);
        if (disabled) {
          return (
            <span key={stage.label} className="disabled">
              {stage.label}
            </span>
          );
        }
        return (
          <Link
            key={stage.label}
            to={path}
            className={i === activeStage ? 'active' : ''}
          >
            {stage.label}
          </Link>
        );
      })}
    </nav>
  );
}
