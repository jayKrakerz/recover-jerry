/**
 * Recovery page — destination, options, progress, report.
 */
import { api } from '../api.js';
import { ws } from '../ws.js';
import { store } from '../state.js';
import { renderProgressBar } from '../components/progress-bar.js';

export async function renderRecovery(container, params) {
    const jobId = params.get('job') || store.get('currentScanJobId');
    const selectedFiles = store.get('selectedFiles');

    if (!jobId || !selectedFiles || selectedFiles.size === 0) {
        container.innerHTML = `
            <div class="alert alert-warning">
                No files selected for recovery. <a href="#/scanner">Start a scan</a> first.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <h1 class="section-title">Recover Files</h1>
        <p class="section-subtitle">${selectedFiles.size} files selected for recovery</p>

        <div class="card mb-2">
            <h3 class="mb-2">Destination</h3>
            <div class="form-group">
                <label for="dest-path">Recovery destination path</label>
                <input type="text" id="dest-path" value="${getDefaultDest()}" placeholder="/Volumes/External/recovered-files">
            </div>
            <div class="checkbox-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="preserve-structure" checked>
                    Preserve directory structure
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="verify-checksums" checked>
                    Verify checksums after copy
                </label>
            </div>
        </div>

        <div class="flex gap-2 mb-2">
            <button class="btn btn-primary" id="start-recovery-btn">Start Recovery</button>
            <a href="#/results/${jobId}" class="btn">Back to Results</a>
        </div>

        <div id="recovery-progress" class="hidden">
            <div class="card">
                <h3 class="mb-2">Recovery Progress</h3>
                <div id="recovery-progress-bar"></div>
                <p class="text-sm text-muted mt-2" id="recovery-message"></p>
            </div>
        </div>

        <div id="recovery-report" class="hidden"></div>
    `;

    const startBtn = container.querySelector('#start-recovery-btn');
    const progressSection = container.querySelector('#recovery-progress');
    const progressBar = container.querySelector('#recovery-progress-bar');
    const message = container.querySelector('#recovery-message');
    const reportSection = container.querySelector('#recovery-report');

    startBtn.addEventListener('click', async () => {
        const dest = container.querySelector('#dest-path').value.trim();
        if (!dest) {
            alert('Please specify a destination path');
            return;
        }

        if (!confirm(`Recover ${selectedFiles.size} files to ${dest}?`)) return;

        const request = {
            job_id: jobId,
            file_ids: [...selectedFiles],
            destination: dest,
            preserve_directory_structure: container.querySelector('#preserve-structure').checked,
            verify_checksums: container.querySelector('#verify-checksums').checked,
        };

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';
        progressSection.classList.remove('hidden');

        try {
            const result = await api.startRecovery(request);
            const recoveryId = result.job_id;
            store.set('currentRecoveryJobId', recoveryId);

            ws.connect();
            setTimeout(() => ws.subscribeRecovery(recoveryId), 500);

            ws.on('recovery_progress', (msg) => {
                if (msg.job_id !== recoveryId) return;
                const p = msg.progress;
                progressBar.innerHTML = renderProgressBar(p.percent || 0);
                message.textContent = p.message || '';

                if (msg.status === 'completed' || msg.status === 'failed') {
                    showReport(reportSection, recoveryId);
                }
            });

            pollRecoveryStatus(recoveryId, progressBar, message, reportSection, startBtn);

        } catch (e) {
            alert(`Recovery failed: ${e.message}`);
            startBtn.disabled = false;
            startBtn.textContent = 'Start Recovery';
        }
    });
}

async function pollRecoveryStatus(recoveryId, progressBar, message, reportSection, startBtn) {
    let done = false;
    while (!done) {
        await new Promise(r => setTimeout(r, 1500));
        try {
            const job = await api.getRecoveryJob(recoveryId);
            const p = job.progress;
            progressBar.innerHTML = renderProgressBar(p.percent || 0);
            message.textContent = p.message || `Status: ${job.status}`;

            if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
                done = true;
                startBtn.disabled = false;
                startBtn.textContent = 'Start Recovery';
                showReport(reportSection, recoveryId, job);
            }
        } catch (e) {
            done = true;
        }
    }
}

async function showReport(el, recoveryId, job) {
    if (!job) {
        try { job = await api.getRecoveryJob(recoveryId); }
        catch { return; }
    }

    el.classList.remove('hidden');

    const results = job.results || [];
    const succeeded = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    el.innerHTML = `
        <div class="card mt-2">
            <h3 class="mb-2">Recovery Report</h3>
            <div class="stats-bar">
                <div class="stat">
                    <span class="stat-value" style="color:var(--success)">${succeeded}</span>
                    <span class="stat-label">Recovered</span>
                </div>
                <div class="stat">
                    <span class="stat-value" style="color:var(--danger)">${failed}</span>
                    <span class="stat-label">Failed</span>
                </div>
            </div>
            <div class="recovery-report">
                ${results.map(r => `
                    <div class="file-result ${r.success ? 'success' : 'failed'}">
                        <span class="status-icon">${r.success ? '✓' : '✗'}</span>
                        <span>${r.original_path}</span>
                        ${r.error ? `<span class="text-muted text-sm" style="margin-left:auto">${r.error}</span>` : ''}
                        ${r.checksum_match === false ? '<span class="text-sm" style="color:var(--warning);margin-left:8px">checksum mismatch</span>' : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function getDefaultDest() {
    return '~/Desktop/recovered-files';
}
