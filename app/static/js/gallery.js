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
            <p class="page-subtitle">Projeção UMAP dos embeddings (vetores de 512 dimensões → 2D). Cada ponto é uma foto, colorida pelo indivíduo. Clique em um ponto para ver a foto.</p>
        </div>

        <div class="card">
            <div class="card-header">
                <h2>Projeção UMAP dos Embeddings da Galeria</h2>
                <div class="embedding-stats" id="embedding-stats"></div>
            </div>
            <div class="card-body">
                <div id="embedding-loading" class="loading-screen">
                    <div class="loading-spinner"></div>
                    <p>Carregando mapa de embeddings...</p>
                </div>
                <div id="plotly-container" class="plotly-container hidden"></div>
            </div>
        </div>
    `;

    // Auto-load the embedding map
    await _loadEmbeddingPlotly();
}

async function _loadEmbeddingPlotly() {
    const loadingEl = document.getElementById('embedding-loading');
    const plotContainer = document.getElementById('plotly-container');
    const statsEl = document.getElementById('embedding-stats');

    try {
        const data = await apiJson('/api/gallery/embedding-map');

        if (!data.points || data.points.length === 0) {
            loadingEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🌐</div>
                    <div class="empty-state-text">Sem dados para visualizar</div>
                    <p class="text-muted">Carregue uma galeria com embeddings primeiro.</p>
                </div>
            `;
            return;
        }

        // Show stats
        if (statsEl) {
            statsEl.innerHTML = `
                <span class="badge badge-completed">${data.total_points} pontos · ${data.unique_labels.length} indivíduos</span>
            `;
        }

        // Group points by label for separate Plotly traces
        const grouped = {};
        data.points.forEach(p => {
            if (!grouped[p.label]) grouped[p.label] = { x: [], y: [], urls: [], label: p.label };
            grouped[p.label].x.push(p.x);
            grouped[p.label].y.push(p.y);
            grouped[p.label].urls.push(p.image_url);
        });

        // Generate colors
        const labels = data.unique_labels;
        const traces = labels.map((label, i) => {
            const hue = (i * 360 / labels.length) % 360;
            const color = `hsl(${hue}, 65%, 50%)`;
            const g = grouped[label];
            return {
                x: g.x,
                y: g.y,
                mode: 'markers',
                type: 'scattergl',
                name: label,
                text: g.urls,
                customdata: g.urls,
                marker: {
                    size: 8,
                    color: color,
                    opacity: 0.75,
                    line: { width: 1, color: 'rgba(255,255,255,0.6)' },
                },
                hovertemplate: `<b>${label}</b><br>x: %{x:.2f}<br>y: %{y:.2f}<extra></extra>`,
            };
        });

        const layout = {
            font: { family: "'Inter', sans-serif", color: '#1D2D44' },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: '#F7F8FA',
            margin: { t: 20, r: 20, b: 50, l: 50 },
            xaxis: {
                title: 'UMAP 1',
                gridcolor: '#E2E8F0',
                zerolinecolor: '#E2E8F0',
            },
            yaxis: {
                title: 'UMAP 2',
                gridcolor: '#E2E8F0',
                zerolinecolor: '#E2E8F0',
            },
            legend: {
                title: { text: 'Indivíduos' },
                itemsizing: 'constant',
                font: { size: 11 },
                bgcolor: 'rgba(255,255,255,0.85)',
                bordercolor: '#E2E8F0',
                borderwidth: 1,
            },
            dragmode: 'zoom',
            hovermode: 'closest',
            height: 600,
        };

        const config = {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['sendDataToCloud', 'autoScale2d'],
            toImageButtonOptions: {
                format: 'png',
                filename: 'dolphinid_embedding_map',
                scale: 2,
            },
        };

        // Hide loading, show plot
        loadingEl.classList.add('hidden');
        plotContainer.classList.remove('hidden');

        Plotly.newPlot(plotContainer, traces, layout, config);

        // Click event: open the dolphin photo in a lightbox
        plotContainer.on('plotly_click', (eventData) => {
            if (eventData.points && eventData.points.length > 0) {
                const point = eventData.points[0];
                const imageUrl = point.customdata;
                const label = point.data.name;
                if (imageUrl) {
                    _openEmbeddingPhotoModal(imageUrl, label);
                }
            }
        });

    } catch (err) {
        loadingEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-text">Erro ao carregar embeddings</div>
                <p class="text-muted">${err.message}</p>
            </div>
        `;
    }
}

/**
 * Open a modal overlay showing the dolphin photo for a clicked embedding point.
 */
function _openEmbeddingPhotoModal(imageUrl, label) {
    // Remove any existing modal
    const existing = document.getElementById('embedding-photo-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'embedding-photo-modal';
    overlay.className = 'embedding-modal-overlay';
    overlay.onclick = (e) => {
        if (e.target === overlay) overlay.remove();
    };

    overlay.innerHTML = `
        <div class="embedding-modal-content" onclick="event.stopPropagation()">
            <div class="embedding-modal-header">
                <span class="embedding-modal-title">Indivíduo ${label}</span>
                <button class="lightbox-close-btn" onclick="document.getElementById('embedding-photo-modal').remove()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <div class="embedding-modal-body">
                <img src="${imageUrl}" alt="${label}" class="embedding-modal-img"
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="embedding-modal-fallback" style="display:none;">
                    <span>🐬</span>
                    <p>Imagem não disponível</p>
                </div>
            </div>
            <div class="embedding-modal-footer">
                <button class="btn btn-primary btn-sm" onclick="navigate('#/gallery/individual?label=${encodeURIComponent(label)}'); document.getElementById('embedding-photo-modal').remove();">
                    Ver todas as fotos de ${label}
                </button>
                <span class="text-muted" style="font-size: 0.8rem;">ESC para fechar</span>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    // ESC to close
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
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
