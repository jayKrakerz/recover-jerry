/**
 * WebSocket client for live progress updates.
 */
class WsClient {
    constructor() {
        this.ws = null;
        this.listeners = new Map();
        this.reconnectTimer = null;
    }

    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${location.host}/api/ws`);

        this.ws.onopen = () => {
            console.log('[ws] connected');
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                const type = msg.type;
                const callbacks = this.listeners.get(type) || [];
                for (const cb of callbacks) cb(msg);
            } catch (e) {
                console.error('[ws] parse error', e);
            }
        };

        this.ws.onclose = () => {
            console.log('[ws] disconnected');
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };

        this.ws.onerror = () => {
            this.ws.close();
        };
    }

    send(msg) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(msg));
        }
    }

    subscribeScan(jobId) {
        this.send({ action: 'subscribe_scan', job_id: jobId });
    }

    subscribeRecovery(jobId) {
        this.send({ action: 'subscribe_recovery', job_id: jobId });
    }

    on(type, callback) {
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(callback);
    }

    off(type, callback) {
        const cbs = this.listeners.get(type) || [];
        this.listeners.set(type, cbs.filter(cb => cb !== callback));
    }
}

export const ws = new WsClient();
