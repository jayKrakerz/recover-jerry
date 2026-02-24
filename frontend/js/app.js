/**
 * App init + hash-based SPA router.
 */
import { renderDashboard } from './pages/dashboard.js';
import { renderScanner } from './pages/scanner.js';
import { renderResults } from './pages/results.js';
import { renderRecovery } from './pages/recovery.js';
import { ws } from './ws.js';

const app = document.getElementById('app');

const routes = {
    '/dashboard': () => renderDashboard(app),
    '/scanner': () => renderScanner(app),
    '/results': (params) => {
        const jobId = params.path || null;
        return renderResults(app, jobId);
    },
    '/recovery': (params) => renderRecovery(app, params.query),
};

function parseHash() {
    const hash = location.hash.slice(1) || '/dashboard';
    // Parse path and query
    const [pathPart, queryString] = hash.split('?');
    const segments = pathPart.split('/').filter(Boolean);
    const route = '/' + segments[0];
    const path = segments.slice(1).join('/') || null;
    const query = new URLSearchParams(queryString || '');
    return { route, path, query };
}

async function navigate() {
    const { route, path, query } = parseHash();

    // Update nav active state
    document.querySelectorAll('.nav-links a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('data-page') === route.slice(1));
    });

    const handler = routes[route];
    if (handler) {
        try {
            await handler({ path, query });
        } catch (e) {
            app.innerHTML = `<div class="alert alert-danger">Error: ${e.message}</div>`;
            console.error(e);
        }
    } else {
        app.innerHTML = `<div class="alert alert-warning">Page not found. <a href="#/dashboard">Go to Dashboard</a></div>`;
    }
}

window.addEventListener('hashchange', navigate);

// Initial load — set default hash without triggering double navigation
if (!location.hash) {
    history.replaceState(null, '', '#/dashboard');
}
navigate();

// Connect WebSocket on load
ws.connect();
