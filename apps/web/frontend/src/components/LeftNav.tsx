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
    if (!projectId) return '#';
    return `/projects/${projectId}/${stage.path}`;
  }

  return (
    <nav className="left-nav">
      <div className="brand">egg</div>
      <div className="brand-sub">AI Research</div>
      {stages.map((stage, i) => (
        <Link
          key={stage.label}
          to={buildPath(stage, i)}
          className={i === activeStage ? 'active' : ''}
        >
          {stage.label}
        </Link>
      ))}
    </nav>
  );
}
