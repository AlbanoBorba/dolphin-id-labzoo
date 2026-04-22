/**
 * DolphinID — Gallery explorer & Embedding visualization
 */

async function renderGalleryPage(container) {
    container.innerHTML = `
        <div class="loading-screen">
            <div class="loading-spinner"></div>
            <p>Carregando galeria...</p>
        </div>
    `;

    try {
        const data = await apiJson('/api/gallery/individuals');

        container.innerHTML = `
            <div class="page-header">
                <h1 class="page-title">Galeria de Indivíduos</h1>
                <p class="page-subtitle">${data.total_individuals} indivíduos conhecidos · ${data.total_images} fotos de referência na galeria</p>
            </div>

            <div class="gallery-grid">
                ${data.individuals.map(ind => `
                    <div class="gallery-card" onclick="navigate('#/gallery/individual?label=${encodeURIComponent(ind.label)}')">
                        <img class="gallery-card-image" 
                             src="/api/gallery/individuals/${encodeURIComponent(ind.label)}/image/0" 
                             alt="${ind.label}"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                             loading="lazy">
                        <div style="display:none; width:100%; height:200px; align-items:center; justify-content:center; background:var(--border-light); color:var(--text-muted); font-size:3rem;">
                            🐬
                        </div>
                        <div class="gallery-card-body">
                            <div class="gallery-card-title">${ind.label}</div>
                            <div class="gallery-card-meta">${ind.total_images} fotos na galeria</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📷</div>
                <div class="empty-state-text">Galeria não disponível</div>
                <p class="text-muted">${err.message}</p>
                <p class="text-muted mt-4">Execute <code class="font-mono">python scripts/setup_artifacts.py</code> para configurar os artefatos.</p>
            </div>
        `;
    }
}

async function renderIndividualPage(container, params) {
    const label = params.get('label');
    if (!label) {
        navigate('#/gallery');
        return;
    }

    container.innerHTML = `
        <div class="loading-screen">
            <div class="loading-spinner"></div>
            <p>Carregando fotos de ${label}...</p>
        </div>
    `;

    try {
        const data = await apiJson(`/api/gallery/individuals/${encodeURIComponent(label)}`);

        // Build image URLs for the lightbox gallery
        const imageUrls = data.images.map((img, i) =>
            `/api/gallery/individuals/${encodeURIComponent(label)}/image/${i}`
        );

        container.innerHTML = `
            <div class="page-header">
                <div class="flex items-center justify-between">
                    <div>
                        <h1 class="page-title">Indivíduo ${data.label}</h1>
                        <p class="page-subtitle">${data.total_images} fotos na galeria de referência · Clique para ampliar</p>
                    </div>
                    <button class="btn btn-ghost" onclick="navigate('#/gallery')">← Voltar à Galeria</button>
                </div>
            </div>

            <div class="gallery-grid" style="grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));">
                ${data.images.map((img, i) => `
                    <div class="gallery-card gallery-card-clickable" onclick="openGalleryLightbox(${JSON.stringify(imageUrls).replace(/"/g, '&quot;')}, ${i}, '${data.label.replace(/'/g, "\\'")}')">
                        <div class="gallery-card-image-wrapper">
                            <img class="gallery-card-image" 
                                 src="/api/gallery/individuals/${encodeURIComponent(label)}/image/${i}"
                                 alt="${label} - ${i}"
                                 onerror="this.style.display='none'"
                                 loading="lazy"
                                 style="height: 180px;">
                            <div class="gallery-card-overlay">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
                            </div>
                        </div>
                        <div class="gallery-card-body" style="padding: 8px 12px;">
                            <div class="gallery-card-meta">Foto ${i + 1}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-text">Indivíduo não encontrado: ${label}</div>
                <button class="btn btn-primary mt-6" onclick="navigate('#/gallery')">Voltar à Galeria</button>
            </div>
        `;
    }
}

async function renderEmbeddingsPage(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1 class="page-title">Espaço Latente</h1>
            <p class="page-subtitle">Projeção t-SNE dos embeddings (vetores de 512 dimensões → 2D). Cada ponto é uma foto, colorida pelo indivíduo.</p>
        </div>

        <div class="card">
            <div class="card-header">
                <h2>Projeção t-SNE dos Embeddings da Galeria</h2>
                <button class="btn btn-primary btn-sm" id="load-tsne-btn" onclick="loadEmbeddingMap()">
                    🔄 Gerar Visualização
                </button>
            </div>
            <div class="card-body">
                <div id="tsne-container" style="position: relative;">
                    <div class="empty-state" id="tsne-placeholder">
                        <div class="empty-state-icon">🌐</div>
                        <div class="empty-state-text">Clique em "Gerar Visualização" para computar o t-SNE</div>
                        <p class="text-muted">Isso pode levar alguns segundos dependendo do tamanho da galeria.</p>
                    </div>
                    <canvas id="tsne-canvas" class="chart-canvas hidden"></canvas>
                </div>

                <div id="tsne-legend" class="hidden mt-4" style="display:flex; flex-wrap:wrap; gap:8px;"></div>
            </div>
        </div>
    `;
}

async function loadEmbeddingMap() {
    const btn = document.getElementById('load-tsne-btn');
    const placeholder = document.getElementById('tsne-placeholder');
    const canvas = document.getElementById('tsne-canvas');
    const legend = document.getElementById('tsne-legend');

    btn.disabled = true;
    btn.textContent = '⏳ Computando...';

    if (placeholder) placeholder.innerHTML = `
        <div class="loading-screen">
            <div class="loading-spinner"></div>
            <p>Computando t-SNE... Isso pode levar até 30 segundos.</p>
        </div>
    `;

    try {
        const data = await apiJson('/api/gallery/embedding-map?max_points=500');

        if (!data.points || data.points.length === 0) {
            if (placeholder) placeholder.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-text">Sem dados para visualizar</div>
                </div>
            `;
            return;
        }

        // Draw on canvas
        if (placeholder) placeholder.classList.add('hidden');
        canvas.classList.remove('hidden');
        legend.classList.remove('hidden');
        legend.style.display = 'flex';

        drawTSNE(canvas, data.points, data.unique_labels);
        renderLegend(legend, data.unique_labels);

        btn.textContent = '🔄 Recarregar';
        btn.disabled = false;
    } catch (err) {
        if (placeholder) placeholder.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-text">Erro ao gerar t-SNE</div>
                <p class="text-muted">${err.message}</p>
            </div>
        `;
        btn.textContent = '🔄 Tentar Novamente';
        btn.disabled = false;
    }
}

function drawTSNE(canvas, points, labels) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    // Set canvas size
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 500 * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = '500px';
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = 500;
    const padding = 40;

    // Clear
    ctx.fillStyle = '#F7F8FA';
    ctx.fillRect(0, 0, w, h);

    // Compute bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    points.forEach(p => {
        minX = Math.min(minX, p.x);
        maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y);
        maxY = Math.max(maxY, p.y);
    });

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    // Color palette
    const colors = generateColors(labels.length);
    const colorMap = {};
    labels.forEach((label, i) => { colorMap[label] = colors[i]; });

    // Draw points
    points.forEach(p => {
        const x = padding + ((p.x - minX) / rangeX) * (w - 2 * padding);
        const y = padding + ((p.y - minY) / rangeY) * (h - 2 * padding);

        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = colorMap[p.label] || '#999';
        ctx.globalAlpha = 0.7;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = 'rgba(255,255,255,0.5)';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
}

function renderLegend(container, labels) {
    const colors = generateColors(labels.length);
    container.innerHTML = labels.map((label, i) => `
        <div style="display:flex; align-items:center; gap:4px; padding:2px 8px; background:white; border-radius:12px; border:1px solid var(--border-light); font-size:0.8rem;">
            <span style="width:10px; height:10px; border-radius:50%; background:${colors[i]}; display:inline-block;"></span>
            <span style="font-weight:600;">${label}</span>
        </div>
    `).join('');
}

function generateColors(n) {
    const colors = [];
    for (let i = 0; i < n; i++) {
        const hue = (i * 360 / n) % 360;
        colors.push(`hsl(${hue}, 65%, 50%)`);
    }
    return colors;
}


// --- Gallery Lightbox with navigation ---

let _galleryLightbox = { urls: [], index: 0, label: '', overlay: null };

function openGalleryLightbox(urls, startIndex, label) {
    _galleryLightbox = { urls, index: startIndex, label, overlay: null };
    _renderGalleryLightbox();
}

function _renderGalleryLightbox() {
    // Remove existing
    if (_galleryLightbox.overlay) {
        _galleryLightbox.overlay.remove();
    }

    const { urls, index, label } = _galleryLightbox;
    const total = urls.length;
    const src = urls[index];
    const hasPrev = index > 0;
    const hasNext = index < total - 1;

    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.onclick = (e) => {
        if (e.target === overlay) _closeGalleryLightbox();
    };

    overlay.innerHTML = `
        <div class="lightbox-content lightbox-gallery" onclick="event.stopPropagation()">
            <div class="lightbox-header">
                <span class="lightbox-title">${label} · Foto ${index + 1} de ${total}</span>
                <button class="lightbox-close-btn" onclick="_closeGalleryLightbox()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <div class="lightbox-body">
                ${hasPrev ? `
                    <button class="lightbox-nav lightbox-nav-prev" onclick="_galleryLightboxNav(-1)">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                    </button>
                ` : ''}
                <img src="${src}" alt="${label} - ${index + 1}" class="lightbox-img" style="max-width: 85vw; max-height: 80vh;">
                ${hasNext ? `
                    <button class="lightbox-nav lightbox-nav-next" onclick="_galleryLightboxNav(1)">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    </button>
                ` : ''}
            </div>
            <div class="lightbox-footer">
                <span class="text-muted" style="font-size: 0.8rem; color: rgba(255,255,255,0.5);">
                    ← → para navegar · ESC para fechar
                </span>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    _galleryLightbox.overlay = overlay;

    // Keyboard navigation
    document.addEventListener('keydown', _galleryLightboxKeyHandler);
}

function _galleryLightboxNav(delta) {
    const newIndex = _galleryLightbox.index + delta;
    if (newIndex >= 0 && newIndex < _galleryLightbox.urls.length) {
        _galleryLightbox.index = newIndex;
        _renderGalleryLightbox();
    }
}

function _closeGalleryLightbox() {
    if (_galleryLightbox.overlay) {
        _galleryLightbox.overlay.remove();
        _galleryLightbox.overlay = null;
    }
    document.removeEventListener('keydown', _galleryLightboxKeyHandler);
}

function _galleryLightboxKeyHandler(e) {
    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        _galleryLightboxNav(-1);
    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        _galleryLightboxNav(1);
    } else if (e.key === 'Escape') {
        _closeGalleryLightbox();
    }
}
