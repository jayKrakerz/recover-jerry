/**
 * API client wrapper.
 */
const API_BASE = '/api';

async function apiFetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

export const api = {
    // System
    getSystemInfo: () => apiFetch('/system/info'),
    refreshSystem: () => apiFetch('/system/refresh', { method: 'POST' }),
    sudoAuth: (password) => apiFetch('/system/sudo', {
        method: 'POST',
        body: JSON.stringify({ password }),
    }),
    sudoStatus: () => apiFetch('/system/sudo/status'),

    // Scan
    startScan: (config) => apiFetch('/scan/start', {
        method: 'POST',
        body: JSON.stringify(config),
    }),
    getScanJob: (jobId) => apiFetch(`/scan/jobs/${jobId}`),
    cancelScan: (jobId) => apiFetch(`/scan/jobs/${jobId}/cancel`, { method: 'POST' }),

    // Results
    getResults: (jobId, params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return apiFetch(`/results/${jobId}${qs ? '?' + qs : ''}`);
    },
    getResultStats: (jobId) => apiFetch(`/results/${jobId}/stats`),

    // Preview
    getPreviewUrl: (jobId, fileId) => `${API_BASE}/preview/${jobId}/${fileId}`,

    // Recovery
    startRecovery: (request) => apiFetch('/recovery/start', {
        method: 'POST',
        body: JSON.stringify(request),
    }),
    getRecoveryJob: (jobId) => apiFetch(`/recovery/jobs/${jobId}`),
};
