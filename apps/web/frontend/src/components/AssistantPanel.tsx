import { useState } from 'react';
import './AssistantPanel.css';

interface ContextChip {
  label: string;
  value: string;
}

interface AssistantPanelProps {
  chips?: ContextChip[];
  actions?: string[];
}

export function AssistantPanel({ chips = [], actions = [] }: AssistantPanelProps) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([
    { role: 'assistant', text: 'How can I help with your research project?' },
  ]);

  function handleSend() {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', text: input }]);
    setInput('');
    // Placeholder — real LLM integration is P12-04
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'I\'ll help with that. (LLM integration coming in P12-04)' },
      ]);
    }, 500);
  }

  return (
    <aside className="assistant">
      <h2>AI Assistant</h2>
      {chips.length > 0 && (
        <div className="chips">
          {chips.map((c) => (
            <span key={c.label} className="chip">{c.label}: {c.value}</span>
          ))}
        </div>
      )}
      <div className="chat-history">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-${msg.role}`}>{msg.text}</div>
        ))}
      </div>
      {actions.length > 0 && (
        <div className="ai-actions">
          {actions.map((a) => (
            <button key={a} className="btn btn-secondary btn-sm">{a}</button>
          ))}
        </div>
      )}
      <div className="chat-input">
        <input
          type="text"
          placeholder="Ask anything..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
        />
        <button className="btn btn-primary btn-sm" onClick={handleSend}>Send</button>
      </div>
    </aside>
  );
}
