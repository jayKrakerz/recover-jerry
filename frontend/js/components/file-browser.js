/**
 * File browser table component.
 */
export function renderFileBrowser(el, data, jobId, options) {
    const { files, total, offset, limit } = data;
    const { onSort, onSelect, onPreview, onPageChange, sortBy, sortOrder, selectedFiles } = options;

    const sortClass = (col) => {
        if (col === sortBy) return sortOrder === 'asc' ? 'sorted-asc' : 'sorted-desc';
        return '';
    };

    const totalPages = Math.ceil(total / limit);
    const currentPage = Math.floor(offset / limit) + 1;

    el.innerHTML = `
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width:30px"><input type="checkbox" id="select-all"></th>
                        <th class="${sortClass('filename')}" data-sort="filename">Name</th>
                        <th class="${sortClass('extension')}" data-sort="extension">Type</th>
                        <th class="${sortClass('size')}" data-sort="size">Size</th>
                        <th class="${sortClass('modified')}" data-sort="modified">Modified</th>
                        <th class="${sortClass('source')}" data-sort="source">Source</th>
                        <th>Path</th>
                        <th style="width:60px"></th>
                    </tr>
                </thead>
                <tbody>
                    ${files.length === 0 ? `
                        <tr><td colspan="8" class="text-muted text-sm" style="text-align:center;padding:24px">No files found</td></tr>
                    ` : files.map(f => `
                        <tr data-id="${f.id}">
                            <td><input type="checkbox" class="file-cb" value="${f.id}" ${selectedFiles.has(f.id) ? 'checked' : ''}></td>
                            <td class="filename" title="${esc(f.filename)}">${esc(f.filename)}</td>
                            <td>${esc(f.extension)}</td>
                            <td class="size">${formatSize(f.metadata?.size || 0)}</td>
                            <td class="text-muted text-sm">${formatDate(f.metadata?.modified || f.metadata?.created)}</td>
                            <td><span class="source-badge badge-available">${esc(f.source_id)}</span></td>
                            <td class="path" title="${esc(f.original_path)}">${esc(f.original_path)}</td>
                            <td><button class="btn btn-sm preview-btn" data-id="${f.id}">Preview</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${totalPages > 1 ? `
            <div class="flex-between mt-2">
                <span class="text-sm text-muted">Showing ${offset + 1}-${Math.min(offset + limit, total)} of ${total}</span>
                <div class="flex gap-2">
                    <button class="btn btn-sm" id="prev-page" ${currentPage <= 1 ? 'disabled' : ''}>Previous</button>
                    <span class="text-sm" style="line-height:30px">Page ${currentPage} of ${totalPages}</span>
                    <button class="btn btn-sm" id="next-page" ${currentPage >= totalPages ? 'disabled' : ''}>Next</button>
                </div>
            </div>
        ` : `
            <div class="mt-2 text-sm text-muted">${total} files</div>
        `}
    `;

    // Sort headers
    el.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => onSort(th.dataset.sort));
    });

    // Checkboxes
    el.querySelectorAll('.file-cb').forEach(cb => {
        cb.addEventListener('change', () => onSelect(cb.value, cb.checked));
    });

    // Select all
    const selectAll = el.querySelector('#select-all');
    if (selectAll) {
        selectAll.addEventListener('change', () => {
            el.querySelectorAll('.file-cb').forEach(cb => {
                cb.checked = selectAll.checked;
                onSelect(cb.value, selectAll.checked);
            });
        });
    }

    // Preview buttons
    el.querySelectorAll('.preview-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const file = files.find(f => f.id === btn.dataset.id);
            if (file) onPreview(file);
        });
    });

    // Pagination
    const prevBtn = el.querySelector('#prev-page');
    const nextBtn = el.querySelector('#next-page');
    if (prevBtn) prevBtn.addEventListener('click', () => onPageChange(offset - limit));
    if (nextBtn) nextBtn.addEventListener('click', () => onPageChange(offset + limit));
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

function formatDate(dt) {
    if (!dt) return '-';
    try {
        const d = new Date(dt);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '-';
    }
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
