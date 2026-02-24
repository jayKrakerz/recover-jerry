/**
 * Scanner page — scan config form + date picker.
 */
import { api } from '../api.js';
import { ws } from '../ws.js';
import { store } from '../state.js';
import { renderProgressBar } from '../components/progress-bar.js';

// Default date range: last 30 days
function defaultStart() {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
}
function defaultEnd() {
    return new Date().toISOString().slice(0, 10);
}

// Cancel polling when page changes
let _pollTimer = null;

function clearPoll() {
    if (_pollTimer) {
        clearInterval(_pollTimer);
        _pollTimer = null;
    }
}

export async function renderScanner(container) {
    // Cancel any previous polling
    clearPoll();
    ws.listeners.delete('scan_progress');

    let info = store.get('systemInfo');
    if (!info) {
        try {
            info = await api.getSystemInfo();
            store.set('systemInfo', info);
        } catch (e) {
            container.innerHTML = `<div class="alert alert-danger">Could not load system info: ${e.message}</div>`;
            return;
        }
    }

    const sources = (info.sources || []).filter(s => s.available || s.source_id === 'trash');

    container.innerHTML = `
        <h1 class="section-title">Configure Scan</h1>
        <p class="section-subtitle">Select sources and date range, then start scanning</p>

        <div class="card mb-2">
            <h3 class="mb-2">Sources</h3>
            <div class="checkbox-group" id="source-checkboxes">
                ${(info.sources || []).map(s => `
                    <label class="checkbox-label">
                        <input type="checkbox" value="${s.source_id}"
                            ${s.available ? 'checked' : 'disabled'}
                            ${!s.available ? 'title="Not available"' : ''}>
                        ${s.name}
                        ${s.requires_sudo ? '<span class="source-badge badge-sudo">sudo</span>' : ''}
                        ${!s.available ? '<span class="source-badge badge-unavailable">N/A</span>' : ''}
                    </label>
                `).join('')}
            </div>
        </div>

        <div class="card mb-2">
            <h3 class="mb-2">Date Range</h3>
            <p class="text-sm text-muted mb-2">Only find files from this period</p>
            <div class="form-row">
                <div class="form-group">
                    <label for="date-start">Start Date</label>
                    <input type="date" id="date-start" value="${defaultStart()}">
                </div>
                <div class="form-group">
                    <label for="date-end">End Date</label>
                    <input type="date" id="date-end" value="${defaultEnd()}">
                </div>
            </div>
        </div>

        <div class="card mb-2">
            <h3 class="mb-2">File Filters (optional)</h3>
            <div class="form-group">
                <label>File Types</label>
                <div class="checkbox-group">
                    <label class="checkbox-label"><input type="checkbox" class="file-type-cb" value="image"> Images</label>
                    <label class="checkbox-label"><input type="checkbox" class="file-type-cb" value="document"> Documents</label>
                    <label class="checkbox-label"><input type="checkbox" class="file-type-cb" value="video"> Videos</label>
                    <label class="checkbox-label"><input type="checkbox" class="file-type-cb" value="audio"> Audio</label>
                    <label class="checkbox-label"><input type="checkbox" class="file-type-cb" value="code"> Code</label>
                </div>
            </div>
            <div class="form-group">
                <label for="extensions-input">Extensions (comma-separated, e.g. .jpg,.pdf)</label>
                <input type="text" id="extensions-input" placeholder=".jpg, .pdf, .docx">
            </div>
        </div>

        <div class="flex gap-2">
            <button class="btn btn-primary" id="start-scan-btn">Start Scan</button>
        </div>

        <div id="scan-progress" class="mt-2 hidden">
            <div class="card">
                <div class="flex-between mb-2">
                    <h3>Scan Progress</h3>
                    <button class="btn btn-sm btn-danger" id="cancel-scan-btn">Cancel</button>
                </div>
                <div id="progress-container"></div>
                <p class="text-sm text-muted mt-2" id="scan-message"></p>
            </div>
        </div>
    `;

    const startBtn = container.querySelector('#start-scan-btn');
    const cancelBtn = container.querySelector('#cancel-scan-btn');
    const progressSection = container.querySelector('#scan-progress');
    const progressContainer = container.querySelector('#progress-container');
    const scanMessage = container.querySelector('#scan-message');

    function updateUI(status, progress, jobId) {
        const p = progress || {};
        progressContainer.innerHTML = renderProgressBar(p.percent || 0);
        scanMessage.textContent = p.message || '';

        if (status === 'completed' || status === 'failed' || status === 'cancelled') {
            clearPoll();
            startBtn.disabled = false;
            startBtn.textContent = 'Start Scan';
            cancelBtn.classList.add('hidden');
            if (status === 'completed') {
                scanMessage.innerHTML = `${p.message || 'Scan complete.'} <a href="#/results/${jobId}" class="btn btn-primary btn-sm" style="margin-left:8px">View Results</a>`;
            }
        }
    }

    startBtn.addEventListener('click', async () => {
        const selectedSources = [...container.querySelectorAll('#source-checkboxes input:checked')]
            .map(cb => cb.value);
        const dateStart = container.querySelector('#date-start').value;
        const dateEnd = container.querySelector('#date-end').value;
        const fileTypes = [...container.querySelectorAll('.file-type-cb:checked')].map(cb => cb.value);
        const extRaw = container.querySelector('#extensions-input').value.trim();
        const extensions = extRaw ? extRaw.split(',').map(e => e.trim()).filter(Boolean) : [];

        if (!selectedSources.length) {
            alert('Select at least one source');
            return;
        }

        const config = {
            sources: selectedSources,
            volume: '/',
        };

        if (dateStart && dateEnd) {
            config.date_range = {
                start: new Date(dateStart + 'T00:00:00').toISOString(),
                end: new Date(dateEnd + 'T23:59:59').toISOString(),
            };
        }
        if (fileTypes.length) config.file_types = fileTypes;
        if (extensions.length) config.file_extensions = extensions;

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        try {
            const result = await api.startScan(config);
            const jobId = result.job_id;
            store.set('currentScanJobId', jobId);

            progressSection.classList.remove('hidden');

            // Primary: WebSocket for real-time updates
            ws.listeners.delete('scan_progress');
            ws.connect();
            setTimeout(() => ws.subscribeScan(jobId), 500);

            ws.on('scan_progress', (msg) => {
                if (msg.job_id !== jobId) return;
                updateUI(msg.status, msg.progress, jobId);
            });

            // Fallback: poll every 15 seconds only as a safety net
            clearPoll();
            _pollTimer = setInterval(async () => {
                try {
                    const job = await api.getScanJob(jobId);
                    updateUI(job.status, job.progress, jobId);
                } catch (e) {
                    clearPoll();
                }
            }, 15000);

        } catch (e) {
            alert(`Scan failed: ${e.message}`);
            startBtn.disabled = false;
            startBtn.textContent = 'Start Scan';
        }
    });

    cancelBtn.addEventListener('click', async () => {
        const jobId = store.get('currentScanJobId');
        if (jobId) {
            try {
                await api.cancelScan(jobId);
            } catch (e) {
                console.error('Cancel failed', e);
            }
        }
    });
}
