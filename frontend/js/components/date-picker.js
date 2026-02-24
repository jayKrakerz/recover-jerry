/**
 * Date picker helper (uses native datetime-local inputs).
 */
export function renderDatePicker(startValue, endValue) {
    return `
        <div class="form-row">
            <div class="form-group">
                <label for="date-start">Start Date</label>
                <input type="datetime-local" id="date-start" value="${startValue || ''}">
            </div>
            <div class="form-group">
                <label for="date-end">End Date</label>
                <input type="datetime-local" id="date-end" value="${endValue || ''}">
            </div>
        </div>
    `;
}

export function getDateRange(container) {
    const start = container.querySelector('#date-start')?.value;
    const end = container.querySelector('#date-end')?.value;
    if (start && end) {
        return {
            start: new Date(start).toISOString(),
            end: new Date(end).toISOString(),
        };
    }
    return null;
}
