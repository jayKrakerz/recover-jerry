/**
 * Results page — file browser + preview.
 */
import { api } from '../api.js';
import { store } from '../state.js';
import { renderFileBrowser } from '../components/file-browser.js';

export async function renderResults(container, jobId) {
    if (!jobId) {
        container.innerHTML = '<div class="alert alert-warning">No scan job specified. <a href="#/scanner">Start a scan</a></div>';
        return;
    }

    container.innerHTML = `
        <div class="flex-between">
            <h1 class="section-title">Scan Results</h1>
            <div class="flex gap-2">
                <button class="btn btn-primary" id="recover-selected-btn" disabled>Recover Selected (0)</button>
                <a href="#/scanner" class="btn">New Scan</a>
            </div>
        </div>
        <div id="stats-container" class="mb-2"></div>
        <div class="search-bar">
            <input type="text" id="search-input" placeholder="Search files...">
            <select id="ext-filter">
                <option value="">All Extensions</option>
            </select>
            <select id="source-filter">
                <option value="">All Sources</option>
            </select>
        </div>
        <div id="file-browser"></div>
        <div id="preview-panel" class="hidden"></div>
    `;

    store.set('selectedFiles', new Set());

    const recoverBtn = container.querySelector('#recover-selected-btn');
    const searchInput = container.querySelector('#search-input');
    const extFilter = container.querySelector('#ext-filter');
    const sourceFilter = container.querySelector('#source-filter');
    const browserEl = container.querySelector('#file-browser');
    const previewEl = container.querySelector('#preview-panel');

    let currentSort = 'filename';
    let currentOrder = 'asc';
    let currentOffset = 0;
    const pageSize = 100;

    // Load stats
    try {
        const stats = await api.getResultStats(jobId);
        const statsContainer = container.querySelector('#stats-container');
        statsContainer.innerHTML = `
            <div class="stats-bar">
                <div class="stat">
                    <span class="stat-value">${stats.total_files}</span>
                    <span class="stat-label">Files Found</span>
                </div>
                <div class="stat">
                    <span class="stat-value">${formatSize(stats.total_size)}</span>
                    <span class="stat-label">Total Size</span>
                </div>
                ${Object.entries(stats.by_source || {}).map(([k, v]) => `
                    <div class="stat">
                        <span class="stat-value">${v}</span>
                        <span class="stat-label">${k}</span>
                    </div>
                `).join('')}
            </div>
        `;

        // Populate extension filter
        for (const ext of Object.keys(stats.by_extension || {}).sort()) {
            const opt = document.createElement('option');
            opt.value = ext;
            opt.textContent = `${ext} (${stats.by_extension[ext]})`;
            extFilter.appendChild(opt);
        }
        for (const src of Object.keys(stats.by_source || {}).sort()) {
            const opt = document.createElement('option');
            opt.value = src;
            opt.textContent = src;
            sourceFilter.appendChild(opt);
        }
    } catch (e) {
        console.error('Failed to load stats', e);
    }

    async function loadFiles() {
        const params = {
            offset: currentOffset,
            limit: pageSize,
            sort_by: currentSort,
            sort_order: currentOrder,
        };
        const search = searchInput.value.trim();
        if (search) params.search = search;
        const ext = extFilter.value;
        if (ext) params.extension = ext;
        const src = sourceFilter.value;
        if (src) params.source = src;

        try {
            const data = await api.getResults(jobId, params);
            renderFileBrowser(browserEl, data, jobId, {
                onSort: (col) => {
                    if (currentSort === col) {
                        currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
                    } else {
                        currentSort = col;
                        currentOrder = 'asc';
                    }
                    loadFiles();
                },
                onSelect: updateSelection,
                onPreview: (file) => showPreview(previewEl, jobId, file),
                onPageChange: (newOffset) => {
                    currentOffset = newOffset;
                    loadFiles();
                },
                sortBy: currentSort,
                sortOrder: currentOrder,
                selectedFiles: store.get('selectedFiles'),
            });
        } catch (e) {
            browserEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
        }
    }

    function updateSelection(fileId, checked) {
        const selected = store.get('selectedFiles');
        if (checked) selected.add(fileId);
        else selected.delete(fileId);
        store.set('selectedFiles', selected);
        recoverBtn.textContent = `Recover Selected (${selected.size})`;
        recoverBtn.disabled = selected.size === 0;
    }

    searchInput.addEventListener('input', debounce(() => { currentOffset = 0; loadFiles(); }, 300));
    extFilter.addEventListener('change', () => { currentOffset = 0; loadFiles(); });
    sourceFilter.addEventListener('change', () => { currentOffset = 0; loadFiles(); });

    recoverBtn.addEventListener('click', () => {
        const selected = store.get('selectedFiles');
        if (selected.size === 0) return;
        store.set('currentScanJobId', jobId);
        location.hash = `#/recovery?job=${jobId}`;
    });

    loadFiles();
}

function showPreview(el, jobId, file) {
    el.classList.remove('hidden');
    const isImage = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.heic'].includes(file.extension.toLowerCase());
    const isText = ['.txt', '.md', '.json', '.js', '.py', '.html', '.css', '.yaml', '.yml', '.sh', '.ts', '.csv', '.xml', '.log'].includes(file.extension.toLowerCase());

    const url = api.getPreviewUrl(jobId, file.id);

    if (isImage) {
        el.innerHTML = `
            <div class="preview-panel">
                <div class="flex-between mb-2">
                    <strong>${file.filename}</strong>
                    <button class="btn btn-sm" onclick="this.closest('.preview-panel').parentElement.classList.add('hidden')">Close</button>
                </div>
                <img src="${url}" alt="${file.filename}">
            </div>
        `;
    } else if (isText) {
        el.innerHTML = `
            <div class="preview-panel">
                <div class="flex-between mb-2">
                    <strong>${file.filename}</strong>
                    <button class="btn btn-sm" onclick="this.closest('.preview-panel').parentElement.classList.add('hidden')">Close</button>
                </div>
                <pre>Loading...</pre>
            </div>
        `;
        fetch(url)
            .then(r => r.text())
            .then(text => {
                const pre = el.querySelector('pre');
                if (pre) pre.textContent = text.slice(0, 50000);
            })
            .catch(() => {
                const pre = el.querySelector('pre');
                if (pre) pre.textContent = 'Failed to load preview';
            });
    } else {
        el.innerHTML = `
            <div class="preview-panel">
                <div class="flex-between mb-2">
                    <strong>${file.filename}</strong>
                    <button class="btn btn-sm" onclick="this.closest('.preview-panel').parentElement.classList.add('hidden')">Close</button>
                </div>
                <p class="text-muted">Preview not available for ${file.extension || 'this file type'}</p>
            </div>
        `;
    }
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
