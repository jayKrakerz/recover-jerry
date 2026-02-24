/**
 * Progress bar component.
 */
export function renderProgressBar(percent, label) {
    const pct = Math.min(100, Math.max(0, percent));
    return `
        <div class="progress-bar">
            <div class="progress-bar-fill" style="width: ${pct}%"></div>
        </div>
        <div class="progress-info">
            <span>${label || ''}</span>
            <span>${pct.toFixed(1)}%</span>
        </div>
    `;
}
