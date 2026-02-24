/**
 * Source availability card component.
 */
export function renderSourceCard(source) {
    const statusClass = source.available ? 'available' : 'unavailable';
    const badgeClass = source.available ? 'badge-available' : 'badge-unavailable';
    const badgeText = source.available ? 'Available' : 'Unavailable';

    return `
        <div class="source-card ${statusClass}">
            <div class="source-header">
                <span class="source-name">${source.name}</span>
                <span class="source-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="source-detail">${source.detail || ''}</div>
            ${source.requires_sudo ? `
                <div class="source-detail">
                    <span class="source-badge badge-sudo">Requires sudo</span>
                    ${source.has_sudo ? ' (cached)' : ''}
                </div>
            ` : ''}
            ${source.count !== null && source.count !== undefined ? `
                <div class="source-detail">${source.count} items</div>
            ` : ''}
        </div>
    `;
}
