import { useState } from 'react';
import { login, signup } from '../services/api';
import './AuthModal.css';

export default function AuthModal({ onLogin }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      if (isSignUp) {
        const data = await signup(username.trim(), email.trim(), password);
        setSuccess('Registration successful! Logging in...');
        onLogin(data.access_token);
      } else {
        const data = await login(email.trim(), password);
        onLogin(data.access_token);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check credentials.');
    }
    setLoading(false);
  };

  return (
    <div className="auth-overlay animate-fade-in">
      <div className="glass-panel auth-card">
        <div className="auth-header">
          <h2>Welcome to AI OS</h2>
          <p>{isSignUp ? 'Create your agent account' : 'Sign in to access your intelligent dashboard'}</p>
        </div>
        
        <form onSubmit={handleSubmit} className="auth-form">
          {isSignUp && (
            <div className="input-group">
              <input 
                type="text" 
                className="glass-input" 
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required={isSignUp}
              />
            </div>
          )}
          <div className="input-group">
            <input 
              type="email" 
              className="glass-input" 
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="input-group">
            <input 
              type="password" 
              className="glass-input" 
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          {error && <div className="error-message">{error}</div>}
          {success && <div className="success-message">{success}</div>}
          
          <button type="submit" className="glass-button primary w-full" disabled={loading}>
            {loading ? 'Authenticating...' : (isSignUp ? 'Sign Up' : 'Sign In')}
          </button>
        </form>

        <div className="auth-toggle">
          <p>
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}
            <button 
              type="button" 
              className="toggle-link" 
              onClick={() => {
                setIsSignUp(!isSignUp);
                setError(null);
                setSuccess(null);
              }}
            >
              {isSignUp ? 'Sign In' : 'Sign Up'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
