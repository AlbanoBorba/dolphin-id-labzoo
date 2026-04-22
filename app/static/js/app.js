/**
 * DolphinID — SPA Router & Core Application Logic
 * 
 * Simple hash-based router that renders views into the #app container.
 */

// --- Utility Functions ---

async function api(endpoint, options = {}) {
    const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response;
}

async function apiJson(endpoint, options = {}) {
    const res = await api(endpoint, options);
    return res.json();
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function confidenceClass(score) {
    if (score >= 0.75) return 'confidence-high';
    if (score >= 0.50) return 'confidence-medium';
    return 'confidence-low';
}

function statusBadge(status) {
    const labels = {
        'pending': 'Pendente',
        'processing': 'Processando',
        'completed': 'Concluído',
        'failed': 'Falhou',
        'identified': 'Identificado',
        'confirmed': 'Confirmado',
        'no_detection': 'Sem Detecção',
        'detected': 'Detectado',
    };
    return `<span class="badge badge-${status}">${labels[status] || status}</span>`;
}

// --- Router ---

let routes = {};

function navigate(hash) {
    window.location.hash = hash;
}

function parseRoute() {
    const hash = window.location.hash.replace('#', '') || '/';
    const [path, queryString] = hash.split('?');
    const params = new URLSearchParams(queryString || '');
    return { path, params };
}

function updateActiveNav(path) {
    document.querySelectorAll('.nav-link').forEach(link => {
        const route = link.dataset.route;
        link.classList.toggle('active',
            (route === 'home' && (path === '/' || path === '' || path === '/home' || path === '/processing' || path === '/results')) ||
            (route === 'gallery' && path.startsWith('/gallery')) ||
            (route === 'embeddings' && path === '/embeddings')
        );
    });
}

async function router() {
    const { path, params } = parseRoute();
    const app = document.getElementById('app');

    updateActiveNav(path);

    // Find matching route
    const handler = routes[path];
    if (handler) {
        try {
            await handler(app, params);
        } catch (err) {
            console.error('Route error:', err);
            app.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">❌</div>
                    <div class="empty-state-text">Erro ao carregar a página</div>
                    <p class="text-muted">${err.message}</p>
                    <button class="btn btn-primary mt-6" onclick="navigate('#/')">Voltar ao Início</button>
                </div>
            `;
        }
    } else {
        app.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <div class="empty-state-text">Página não encontrada</div>
                <button class="btn btn-primary mt-6" onclick="navigate('#/')">Voltar ao Início</button>
            </div>
        `;
    }
}

// --- System Status ---

async function updateSystemStatus() {
    try {
        const config = await apiJson('/api/config');
        const dot = document.querySelector('.status-dot');
        const text = document.querySelector('.status-text');

        if (config.model_exists && config.gallery_loaded) {
            dot.className = 'status-dot ready';
            text.textContent = `${config.gallery_individuals} indivíduos | ${config.gallery_images} fotos`;
        } else if (!config.model_exists) {
            dot.className = 'status-dot error';
            text.textContent = 'Modelo não encontrado';
        } else {
            dot.className = 'status-dot';
            text.textContent = 'Gallery não carregada';
        }
    } catch {
        const dot = document.querySelector('.status-dot');
        const text = document.querySelector('.status-text');
        if (dot) dot.className = 'status-dot error';
        if (text) text.textContent = 'Offline';
    }
}

// --- Initialize ---

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', () => {
    // Initialize routes here so all script files have loaded their functions
    routes = {
        '': renderHomePage,
        '/': renderHomePage,
        '/home': renderHomePage,
        '/processing': renderProcessingPage,
        '/results': renderResultsPage,
        '/gallery': renderGalleryPage,
        '/gallery/individual': renderIndividualPage,
        '/embeddings': renderEmbeddingsPage,
    };
    router();
    updateSystemStatus();
    // Refresh status every 30s
    setInterval(updateSystemStatus, 30000);
});
