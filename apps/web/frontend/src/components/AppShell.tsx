import type { ReactNode } from 'react';
import { LeftNav } from './LeftNav';
import { AssistantPanel } from './AssistantPanel';
import './AppShell.css';

interface ContextChip {
  label: string;
  value: string;
}

interface AppShellProps {
  children: ReactNode;
  currentStage?: number;
  projectId?: string;
  chips?: ContextChip[];
  actions?: string[];
}

const STAGES = [
  { label: 'Home', path: '/' },
  { label: 'Project Setup', path: '/projects/new' },
  { label: 'Brief Review', path: 'brief' },
  { label: 'Survey Builder', path: 'survey' },
  { label: 'Data Mapping', path: 'mapping' },
  { label: 'Analysis', path: 'analysis' },
  { label: 'Reporting', path: 'report' },
];

export function AppShell({ children, currentStage = 0, projectId, chips, actions }: AppShellProps) {
  return (
    <div className="layout">
      <LeftNav stages={STAGES} activeStage={currentStage} projectId={projectId} />
      <main className="main">{children}</main>
      <AssistantPanel chips={chips} actions={actions} />
    </div>
  );
}
