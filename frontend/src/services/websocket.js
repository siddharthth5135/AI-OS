export class ChatWebSocket {
  constructor(token, onMessage, onError, onConnect) {
    this.token = token;
    this.url = `ws://127.0.0.1:8000/ws/chat?token=${token}`;
    this.ws = null;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onConnect = onConnect;
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      if (this.onConnect) this.onConnect();
    };
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this.onMessage) this.onMessage(data);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };
    this.ws.onerror = (err) => {
      if (this.onError) this.onError(err);
    };
    this.ws.onclose = () => {
      console.log('WS Disconnected');
    };
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(message);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
