import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth';
import '../components/AppShell.css';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError('Invalid email or password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'var(--bg)' }}>
      <div className="card" style={{ width: 380, padding: 32 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div className="brand" style={{ fontSize: 36, color: 'var(--accent)' }}>egg</div>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>AI Research Platform</div>
        </div>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: 12 }}>
            <span style={{ fontSize: 14, color: 'var(--muted)' }}>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="researcher@egg.local"
              required
              style={{ display: 'block', width: '100%', padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 10, marginTop: 4, fontSize: 14, background: '#fffdfa' }}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 16 }}>
            <span style={{ fontSize: 14, color: 'var(--muted)' }}>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              required
              style={{ display: 'block', width: '100%', padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 10, marginTop: 4, fontSize: 14, background: '#fffdfa' }}
            />
          </label>
          {error && <div style={{ color: 'var(--warn)', fontSize: 14, marginBottom: 12 }}>{error}</div>}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '10px 16px' }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <div style={{ marginTop: 16, fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>
          Default: researcher@egg.local / password
        </div>
      </div>
    </div>
  );
}
