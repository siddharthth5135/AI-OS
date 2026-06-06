import { Upload, Database, Settings, LogOut, TerminalSquare } from 'lucide-react';
import './Sidebar.css';

export default function Sidebar({ user, onLogout }) {
  return (
    <div className="sidebar glass-panel">
      <div className="brand">
        <TerminalSquare size={28} color="var(--primary-color)" />
        <h2>AI OS</h2>
      </div>

      <div className="nav-menu">
        <div className="nav-item active">
          <Database size={18} />
          <span>Core Chat</span>
        </div>
        <div className="nav-item">
          <Upload size={18} />
          <span>Documents</span>
        </div>
        <div className="nav-item">
          <Settings size={18} />
          <span>Settings</span>
        </div>
      </div>

      <div className="user-profile">
        <div className="avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</div>
        <div className="user-info">
          <span className="username">{user?.username || 'User'}</span>
          <span className="role">{user?.role || 'Admin'}</span>
        </div>
        <button onClick={onLogout} className="logout-btn">
          <LogOut size={16} />
        </button>
      </div>
    </div>
  );
}
