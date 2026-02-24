/**
 * Dashboard page — system overview + source cards + sudo auth.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { renderSourceCard } from '../components/source-card.js';

export async function renderDashboard(container) {
    container.innerHTML = `
        <h1 class="section-title">Dashboard</h1>
        <p class="section-subtitle">System overview and recovery source availability</p>
        <div id="system-status" class="mb-2"></div>
        <div id="sudo-section" class="mb-2"></div>
        <div id="system-alerts" class="mb-2"></div>
        <div class="flex-between mb-2">
            <h3>Recovery Sources</h3>
            <button class="btn btn-sm" id="refresh-btn">Refresh</button>
        </div>
        <div class="card-grid" id="source-cards">
            <div class="text-muted text-sm">Loading...</div>
        </div>
        <div class="mt-2">
            <a href="#/scanner" class="btn btn-primary">Start a Scan</a>
        </div>
    `;

    const refreshBtn = container.querySelector('#refresh-btn');
    refreshBtn.addEventListener('click', async () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = 'Refreshing...';
        try {
            const info = await api.refreshSystem();
            store.set('systemInfo', info);
            renderInfo(container, info);
        } catch (e) {
            console.error(e);
        }
        refreshBtn.disabled = false;
        refreshBtn.textContent = 'Refresh';
    });

    try {
        const info = await api.refreshSystem();
        store.set('systemInfo', info);
        renderInfo(container, info);
    } catch (e) {
        container.querySelector('#source-cards').innerHTML = `
            <div class="alert alert-danger">Failed to load system info: ${e.message}</div>
        `;
    }
}

function renderInfo(container, info) {
    // System status bar
    const statusEl = container.querySelector('#system-status');
    statusEl.innerHTML = `
        <div class="card">
            <div class="stats-bar">
                <div class="stat">
                    <span class="stat-value">${info.hostname || 'Unknown'}</span>
                    <span class="stat-label">Hostname</span>
                </div>
                <div class="stat">
                    <span class="stat-value">${info.os_version || 'Unknown'}</span>
                    <span class="stat-label">OS Version</span>
                </div>
                <div class="stat">
                    <span class="stat-value">${info.has_full_disk_access ? 'Yes' : 'Unknown'}</span>
                    <span class="stat-label">Full Disk Access</span>
                </div>
            </div>
        </div>
    `;

    // Sudo authentication section
    const sudoEl = container.querySelector('#sudo-section');
    const hasSudo = info.sources?.find(s => s.source_id === 'file_carving')?.has_sudo;

    if (hasSudo) {
        sudoEl.innerHTML = `
            <div class="alert alert-success">
                Sudo authenticated — PhotoRec and APFS snapshots are unlocked.
            </div>
        `;
    } else {
        sudoEl.innerHTML = `
            <div class="card">
                <h3 class="mb-2">Unlock Advanced Scanners</h3>
                <p class="text-sm text-muted mb-2">
                    Enter your macOS password to enable PhotoRec file carving and APFS snapshot scanning.
                    The password is only used for sudo and is not stored to disk.
                </p>
                <div class="flex gap-2" style="align-items:flex-end">
                    <div class="form-group" style="flex:1;margin-bottom:0">
                        <label for="sudo-password">macOS Password</label>
                        <input type="password" id="sudo-password" placeholder="Enter your password">
                    </div>
                    <button class="btn btn-primary" id="sudo-btn">Authenticate</button>
                </div>
                <div id="sudo-error" class="mt-2"></div>
            </div>
        `;

        const pwInput = container.querySelector('#sudo-password');
        const sudoBtn = container.querySelector('#sudo-btn');
        const errEl = container.querySelector('#sudo-error');

        async function doAuth() {
            const pw = pwInput.value;
            if (!pw) return;
            sudoBtn.disabled = true;
            sudoBtn.textContent = 'Authenticating...';
            errEl.innerHTML = '';
            try {
                await api.sudoAuth(pw);
                pwInput.value = '';
                // Refresh everything
                const newInfo = await api.refreshSystem();
                store.set('systemInfo', newInfo);
                renderInfo(container, newInfo);
            } catch (e) {
                errEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
            }
            sudoBtn.disabled = false;
            sudoBtn.textContent = 'Authenticate';
        }

        sudoBtn.addEventListener('click', doAuth);
        pwInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') doAuth();
        });
    }

    // Alerts
    const alertsEl = container.querySelector('#system-alerts');
    let alerts = '';
    const sources = info.sources || [];
    const trash = sources.find(s => s.source_id === 'trash');
    const tm = sources.find(s => s.source_id === 'time_machine');

    if (trash && trash.count === 0) {
        alerts += `
            <div class="alert alert-info">
                <strong>Trash is empty.</strong> Use <strong>File Carving (PhotoRec)</strong> to scan raw disk for permanently deleted files.
            </div>
        `;
    }

    if (tm && !tm.available) {
        alerts += `
            <div class="alert alert-info">
                <strong>No Time Machine backups found.</strong> Connect your Time Machine drive and click Refresh.
            </div>
        `;
    }

    alertsEl.innerHTML = alerts;

    // Source cards
    const cardsEl = container.querySelector('#source-cards');
    if (sources.length) {
        cardsEl.innerHTML = sources.map(s => renderSourceCard(s)).join('');
    } else {
        cardsEl.innerHTML = '<div class="text-muted text-sm">No sources detected</div>';
    }
}
