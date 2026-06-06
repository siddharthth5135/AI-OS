import { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Activity } from 'lucide-react';
import { ChatWebSocket } from '../services/websocket';
import './ChatArea.css';

export default function ChatArea({ token }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [orchestratorState, setOrchestratorState] = useState(null);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!token) return;

    wsRef.current = new ChatWebSocket(
      token,
      (eventData) => {
        if (eventData.type === 'token') {
          const text = eventData.data?.text || '';
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'bot') {
              return [...prev.slice(0, -1), { ...last, content: last.content + text }];
            }
            return [...prev, { role: 'bot', content: text }];
          });
          setOrchestratorState(null); // Clear state when typing starts
        } else if (eventData.type === 'task_update') {
          setOrchestratorState({
            status: eventData.data?.status,
            agent_type: eventData.data?.agent
          });
        } else if (eventData.type === 'task_completed') {
          setOrchestratorState(null);
        } else if (eventData.type === 'error') {
          const errorMsg = eventData.data?.message || 'Processing failed';
          setMessages(prev => [...prev, { role: 'bot', content: `Error: ${errorMsg}` }]);
          setOrchestratorState(null);
        }
      },
      (err) => console.error('WS Error:', err),
      () => setConnected(true)
    );

    wsRef.current.connect();
    return () => wsRef.current.disconnect();
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || !connected) return;
    
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      query: input,
      doc_ids: []
    }));
    setInput('');
  };

  return (
    <div className="chat-container">
      <div className="chat-header glass-panel">
        <div className="status-indicator">
          <div className={`status-dot ${connected ? 'glow-active' : ''}`}></div>
          <span>{connected ? 'AI Core Online' : 'Connecting...'}</span>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message animate-fade-in ${msg.role}`}>
            <div className="avatar glass-panel">
              {msg.role === 'user' ? <User size={20} /> : <Bot size={20} color="var(--primary-color)"/>}
            </div>
            <div className="message-content glass-panel">
              {msg.content}
            </div>
          </div>
        ))}
        
        {orchestratorState && (
          <div className="orchestrator-status animate-fade-in glass-panel">
            <Activity size={16} className="spin-icon text-secondary" />
            <span className="text-secondary ml-2">
              Agent Orchestrator: {orchestratorState.status} {orchestratorState.agent_type && `[${orchestratorState.agent_type}]`}
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="chat-input-area glass-panel">
        <input 
          type="text" 
          className="glass-input no-border" 
          placeholder="Ask the AI OS..." 
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className="glass-button primary icon-btn" disabled={!connected || !input.trim()}>
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
