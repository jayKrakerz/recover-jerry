/**
 * Simple pub/sub state store.
 */
class Store {
    constructor() {
        this.state = {
            systemInfo: null,
            currentScanJobId: null,
            currentRecoveryJobId: null,
            selectedFiles: new Set(),
        };
        this.listeners = new Map();
    }

    get(key) {
        return this.state[key];
    }

    set(key, value) {
        this.state[key] = value;
        this._notify(key, value);
    }

    on(key, callback) {
        if (!this.listeners.has(key)) this.listeners.set(key, []);
        this.listeners.get(key).push(callback);
    }

    off(key, callback) {
        const cbs = this.listeners.get(key) || [];
        this.listeners.set(key, cbs.filter(cb => cb !== callback));
    }

    _notify(key, value) {
        const cbs = this.listeners.get(key) || [];
        for (const cb of cbs) cb(value);
    }
}

export const store = new Store();
