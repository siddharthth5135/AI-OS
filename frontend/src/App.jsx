import { useState, useEffect } from 'react';
import AuthModal from './components/AuthModal';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import { getMe } from './services/api';
import './App.css';

function App() {
  const [token, setToken] = useState(localStorage.getItem('ai_os_token'));
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem('ai_os_token', token);
      getMe(token).then(setUser).catch(() => handleLogout());
    } else {
      localStorage.removeItem('ai_os_token');
      setUser(null);
    }
  }, [token]);

  const handleLogout = () => {
    setToken(null);
  };

  return (
    <div className="app-layout">
      {!token ? (
        <AuthModal onLogin={setToken} />
      ) : (
        <>
          <Sidebar user={user} onLogout={handleLogout} />
          <main className="main-content animate-fade-in">
            <ChatArea token={token} />
          </main>
        </>
      )}
    </div>
  );
}

export default App;
