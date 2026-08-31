/**
 * DolphinID — Results / Review page (Phase 4 — Crop-based workflow)
 */


// ─── Sort order for result statuses ─────────────────────────────────────────
const _statusOrder = { needs_review: 0, no_detection: 1, cataloged: 2, discarded: 3 };
function _sortResults(results) {
    return [...results].sort((a, b) => {
        const oa = _statusOrder[a.status] ?? 99;
        const ob = _statusOrder[b.status] ?? 99;
        return oa - ob;
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main page renderer
// ═══════════════════════════════════════════════════════════════════════════════
let _currentSessionId = null;

async function renderResultsPage(container, params) {
    const sessionId = params.get('id');
    if (!sessionId) { navigate('#/'); return; }
    _currentSessionId = sessionId;

    container.innerHTML = `
        <div class="loading-screen">
            <div class="loading-spinner"></div>
            <p>Carregando resultados...</p>
        </div>
    `;

    try {
        const [sessionData, data] = await Promise.all([
            apiJson(`/api/sessions/${sessionId}`),
            apiJson(`/api/sessions/${sessionId}/results`),
        ]);

        const results    = data.results || [];
        const needsReview = results.filter(r => r.status === 'needs_review');
        const noDetect    = results.filter(r => r.status === 'no_detection');
        const cataloged   = results.filter(r => r.status === 'cataloged');
        const discarded   = results.filter(r => r.status === 'discarded');

        container.innerHTML = `
            <div class="page-header">
                <div class="flex items-center justify-between">
                    <div>
                        <h1 class="page-title">Resultados</h1>
                        <p class="page-subtitle">${data.total} imagens processadas</p>
                    </div>
                    <div class="flex gap-2">
                        <a href="/api/export/${sessionId}/csv" class="btn btn-secondary btn-sm">📥 Exportar CSV</a>
                        <a href="/api/export/${sessionId}/report" target="_blank" class="btn btn-secondary btn-sm">📄 Relatório HTML</a>
                        <button class="btn btn-ghost btn-sm" onclick="navigate('#/')">← Voltar</button>
                    </div>
                </div>
            </div>

            <div class="grid-stats">
                <div class="stat-card">
                    <div class="stat-number">${results.length}</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-pending)">${needsReview.length}</div>
                    <div class="stat-label">Revisão Pendente</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-no-detection)">${noDetect.length}</div>
                    <div class="stat-label">Sem Detecção</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-confirmed)">${cataloged.length}</div>
                    <div class="stat-label">Catalogadas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-failed)">${discarded.length}</div>
                    <div class="stat-label">Descartadas</div>
                </div>
            </div>

            <!-- Filters -->
            <div class="card mb-6">
                <div class="card-body" style="padding: 12px 20px;">
                    <div class="flex items-center gap-4" style="flex-wrap:wrap;">
                        <label class="form-label" style="margin: 0; white-space: nowrap;">Filtrar:</label>
                        <select class="form-select" id="filter-status" onchange="filterResults(${sessionId})" style="width: auto; min-width: 180px;">
                            <option value="">Todos</option>
                            <option value="needs_review">Pendentes de Revisão</option>
                            <option value="no_detection">Sem Detecção</option>
                            <option value="cataloged">Catalogadas</option>
                            <option value="discarded">Descartadas</option>
                        </select>
                        <label class="form-label" style="margin: 0; white-space: nowrap;">Confiança mínima:</label>
                        <input type="range" id="filter-confidence" min="0" max="100" value="0"
                               oninput="document.getElementById('conf-value').textContent = this.value + '%'"
                               onchange="filterResults(${sessionId})"
                               style="width: 120px;">
                        <span id="conf-value" class="text-muted" style="min-width: 40px;">0%</span>
                    </div>
                </div>
            </div>

            <div id="results-list">
                ${renderResultsList(results)}
            </div>
        `;
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-text">Erro ao carregar resultados</div>
                <p class="text-muted">${err.message}</p>
                <button class="btn btn-primary mt-6" onclick="navigate('#/')">Voltar</button>
            </div>
        `;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Render a list of result cards
// ═══════════════════════════════════════════════════════════════════════════════
function renderResultsList(results) {
    if (!results || results.length === 0) {
        return `<div class="empty-state"><div class="empty-state-text">Nenhum resultado encontrado</div></div>`;
    }

    const sorted = _sortResults(results);

    return sorted.map(r => {
        const originalSrc = `/api/results/${r.id}/original`;
        let cardMod = '';
        if (r.status === 'cataloged') cardMod = 'review-card--cataloged';
        if (r.status === 'discarded') cardMod = 'review-card--discarded';
        if (r.status === 'no_detection') cardMod = 'review-card--no-detection';

        // ── No detection ─────────────────────────────────────────
        if (r.status === 'no_detection') {
            return `
                <div class="review-card ${cardMod}" id="result-${r.id}">
                    <div class="review-original">
                        <img class="review-original-img" src="${originalSrc}" alt="${r.original_filename}"
                             onclick="openOriginalModal(${r.id}, '${_esc(r.original_filename)}')"
                             loading="lazy"
                             onerror="this.style.display='none'">
                        <span class="review-original-name">${r.original_filename}</span>
                    </div>
                    <div class="review-no-detection">
                        <div class="review-no-detection-icon">🔍</div>
                        <div>Nenhum crop detectado nesta imagem</div>
                        <button class="btn btn-danger btn-sm" onclick="discardResult(${r.id})">
                            ❌ Descartar imagem
                        </button>
                    </div>
                </div>
            `;
        }

        // ── Normal card with crops ───────────────────────────────
        const crops = r.crops || [];
        const cropsHtml = crops.map(c => _renderCropItem(c, r)).join('');

        return `
            <div class="review-card ${cardMod}" id="result-${r.id}">
                <div class="review-original">
                    <img class="review-original-img" src="${originalSrc}" alt="${r.original_filename}"
                         onclick="openOriginalModal(${r.id}, '${_esc(r.original_filename)}')"
                         loading="lazy"
                         onerror="this.style.display='none'">
                    <span class="review-original-name">${r.original_filename}</span>
                </div>
                <div class="review-crops">
                    <div class="review-crops-header">
                        <div class="flex items-center gap-3">
                            ${statusBadge(r.status)}
                            <span class="review-crop-count">${r.crop_count || crops.length} crop(s) detectados</span>
                        </div>
                        ${r.status === 'needs_review' ? `
                            <button class="btn btn-ghost btn-sm text-muted" onclick="discardResult(${r.id})">
                                Descartar Imagem
                            </button>
                        ` : ''}
                    </div>
                    ${cropsHtml}
                </div>
            </div>
        `;
    }).join('');
}

// ─── Render a single crop item ───────────────────────────────────────────────
function _renderCropItem(c) {
    const cropSrc = `/api/results/crop/${c.id}/image`;
    const matches = c.top5_matches || [];
    const yoloPct = c.yolo_confidence != null ? (c.yolo_confidence * 100).toFixed(0) : null;
    const matchPct = c.match_confidence != null ? (c.match_confidence * 100).toFixed(0) : null;

    // Top-K match chips
    const matchChips = matches.map((m, i) => `
        <span class="crop-match-chip ${i === 0 ? 'best' : ''}"
              onclick="classifyCrop(${c.id}, '${_esc(m.id)}')"
              title="Classificar como ${m.id}">
            ${m.id} <span class="crop-match-score">${(m.score * 100).toFixed(0)}%</span>
        </span>
    `).join('');

    // Actions based on crop status
    let actionsHtml = '';
    if (c.status === 'pending') {
        const predLabel = c.predicted_id ? _esc(c.predicted_id) : '';
        actionsHtml = `
            ${c.predicted_id ? `<button class="btn btn-success btn-sm" onclick="classifyCrop(${c.id}, '${predLabel}')">
                ✅ Aprovar como ${c.predicted_id}
            </button>` : ''}
            <button class="btn btn-secondary btn-sm" onclick="approveCrop(${c.id})">
                ✅ Aprovar sem classificar
            </button>
            <button class="btn btn-ghost btn-sm" onclick="showCustomClassify(${c.id})">
                🔄 Outro ID...
            </button>
            <button class="btn btn-danger btn-sm" onclick="rejectCrop(${c.id})">
                ❌ Descartar
            </button>
        `;
    } else if (c.status === 'approved') {
        actionsHtml = `
            <span class="crop-card-status" style="color: #004085;">
                ✅ Aprovado (não classificado)
            </span>
            <button class="btn btn-primary btn-sm" onclick="showCustomClassify(${c.id})">
                🏷️ Classificar...
            </button>
        `;
    } else if (c.status === 'classified') {
        actionsHtml = `
            <span class="crop-card-status" style="color: var(--status-confirmed);">
                ✅ Classificado como ${c.confirmed_id || '?'}
            </span>
        `;
    } else if (c.status === 'discarded') {
        actionsHtml = `
            <span class="crop-card-status" style="color: var(--text-muted);">
                ❌ Descartado
            </span>
        `;
    }

    let cardMod = '';
    if (c.status === 'classified') cardMod = 'crop-card--classified';
    if (c.status === 'approved') cardMod = 'crop-card--approved';
    if (c.status === 'discarded') cardMod = 'crop-card--discarded';

    const yoloClassLabel = c.yolo_class ? c.yolo_class : '';

    return `
        <div class="crop-card ${cardMod}" id="crop-${c.id}">
            <img class="crop-card-img" src="${cropSrc}" alt="Crop ${c.crop_index}"
                 loading="lazy"
                 style="cursor: pointer;"
                 onclick="openCropModal(${c.id}, ${c.crop_index})"
                 title="Clique para ampliar"
                 onerror="this.style.display='none'">
            <div class="crop-card-info">
                <div class="crop-card-header">
                    <span class="text-muted" style="font-size:0.75rem;font-weight:600;text-transform:uppercase;">Crop ${c.crop_index}</span>
                    <div class="flex items-center gap-2" style="flex-wrap:wrap;">
                        ${yoloClassLabel ? `<span style="font-size:0.7rem;padding:2px 6px;border-radius:4px;background:var(--border-light);color:var(--text-muted);">${yoloClassLabel}</span>` : ''}
                        ${yoloPct != null ? `<span class="crop-card-yolo" title="YOLO confidence">YOLO ${yoloPct}%</span>` : ''}
                    </div>
                </div>
                <div class="crop-card-prediction">
                    ${c.predicted_id ? `<span style="font-size:1.1rem;font-weight:800;color:var(--ocean-deep);">${c.predicted_id}</span>` : '<span class="text-muted">—</span>'}
                    ${matchPct != null ? `<span class="result-confidence ${confidenceClass(c.match_confidence)}">${matchPct}%</span>` : ''}
                </div>
                ${matches.length > 0 && c.status === 'pending' ? `
                    <div>
                        <div class="text-muted" style="font-size:0.75rem;margin-bottom:4px;">Top matches:</div>
                        <div class="crop-matches-row">${matchChips}</div>
                    </div>
                ` : ''}
                <div class="crop-card-actions">
                    ${actionsHtml}
                </div>
            </div>
        </div>
    `;
}

// ─── Helper: escape single quotes for inline onclick strings ────────────────
function _esc(s) {
    return String(s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ═══════════════════════════════════════════════════════════════════════════════
// Filter results
// ═══════════════════════════════════════════════════════════════════════════════
async function filterResults(sessionId) {
    const status = document.getElementById('filter-status')?.value;
    const minConf = parseInt(document.getElementById('filter-confidence')?.value || 0) / 100;

    let url = `/api/sessions/${sessionId}/results`;
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (minConf > 0) params.set('min_confidence', minConf.toString());
    if (params.toString()) url += '?' + params.toString();

    try {
        const data = await apiJson(url);
        document.getElementById('results-list').innerHTML = renderResultsList(data.results || []);
    } catch (err) {
        showToast('Erro ao filtrar: ' + err.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Crop action functions
// ═══════════════════════════════════════════════════════════════════════════════
async function approveCrop(cropId) {
    try {
        await apiJson(`/api/results/crop/${cropId}/approve`, { method: 'POST' });
        await _refreshCropInPlace(cropId);
        showToast('Crop aprovado', 'success');
    } catch (err) {
        showToast('Erro ao aprovar crop: ' + err.message, 'error');
    }
}

async function classifyCrop(cropId, label) {
    try {
        await apiJson(`/api/results/crop/${cropId}/classify`, {
            method: 'POST',
            body: JSON.stringify({ individual_label: label }),
        });
        await _refreshCropInPlace(cropId);
        showToast(`Classificado como ${label}`, 'success');
    } catch (err) {
        showToast('Erro ao classificar crop: ' + err.message, 'error');
    }
}

async function rejectCrop(cropId) {
    try {
        await apiJson(`/api/results/crop/${cropId}/reject`, { method: 'POST' });
        await _refreshCropInPlace(cropId);
        showToast('Crop descartado', 'success');
    } catch (err) {
        showToast('Erro ao descartar crop: ' + err.message, 'error');
    }
}

async function discardResult(resultId) {
    if (!confirm('Descartar esta imagem e todos seus crops?')) return;
    try {
        await apiJson(`/api/results/${resultId}/discard`, { method: 'POST' });
        // Update card in-place
        const card = document.getElementById(`result-${resultId}`);
        if (card) {
            card.style.opacity = '0.45';
            const badge = card.querySelector('.badge');
            if (badge) { badge.className = 'badge badge-discarded'; badge.textContent = 'Descartada'; }
            // Remove action buttons
            const actions = card.querySelectorAll('.crop-actions');
            actions.forEach(a => { a.innerHTML = '<span class="crop-status-text" style="color:var(--text-muted);">❌ Descartada</span>'; });
        }
        showToast('Imagem descartada', 'success');
    } catch (err) {
        showToast('Erro ao descartar imagem: ' + err.message, 'error');
    }
}

function showCustomClassify(cropId) {
    const customId = prompt('Digite o ID do indivíduo (ex: #5):');
    if (customId && customId.trim()) {
        classifyCrop(cropId, customId.trim());
    }
}

// ─── Refresh a single crop element after action ──────────────────────────────
async function _refreshCropInPlace(cropId) {
    // We need to re-fetch the parent result to get updated crop data.
    // The crop element id tells us where to put the new HTML.
    if (!_currentSessionId) return;
    try {
        const data = await apiJson(`/api/sessions/${_currentSessionId}/results`);
        const results = data.results || [];
        // Find the crop in results
        for (const r of results) {
            const crops = r.crops || [];
            const crop = crops.find(c => c.id === cropId);
            if (crop) {
                const el = document.getElementById(`crop-${cropId}`);
                if (el) {
                    el.outerHTML = _renderCropItem(crop, r);
                }
                // Also update parent card badge
                const card = document.getElementById(`result-${r.id}`);
                if (card) {
                    const badge = card.querySelector(':scope > .result-info > .flex > .badge');
                    if (badge) {
                        const tmp = document.createElement('div');
                        tmp.innerHTML = statusBadge(r.status);
                        badge.replaceWith(tmp.firstElementChild);
                    }
                }
                break;
            }
        }
    } catch (err) {
        // Silently fail — the toast already showed the action result
        console.warn('Could not refresh crop in-place:', err);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Original image modal / lightbox
// ═══════════════════════════════════════════════════════════════════════════════
function openOriginalModal(resultId, filename) {
    // Remove any existing modal
    const existing = document.getElementById('original-modal');
    if (existing) existing.remove();

    const imgSrc = `/api/results/${resultId}/original`;

    const overlay = document.createElement('div');
    overlay.id = 'original-modal';
    overlay.style.cssText = 'position: fixed; inset: 0; background: rgba(0,0,0,0.88); z-index: 500; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    
    overlay.innerHTML = `
        <div onclick="event.stopPropagation()" style="max-width: 92vw; max-height: 92vh; display: flex; flex-direction: column; align-items: center;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 8px 0; color: #fff;">
                <span style="font-family: var(--font-mono); font-size: 0.85rem; opacity: 0.8;">${filename || 'Imagem original'}</span>
                <button class="lightbox-close-btn" onclick="document.getElementById('original-modal').remove()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <img src="${imgSrc}" alt="${filename}" style="max-width: 90vw; max-height: 82vh; object-fit: contain; border-radius: var(--radius-md); box-shadow: 0 8px 40px rgba(0,0,0,0.5);"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            <div class="embedding-modal-fallback" style="display:none;">
                <span>🐬</span>
                <p>Imagem não disponível</p>
            </div>
            <div style="text-align:center;padding:8px 0;">
                <span class="text-muted" style="font-size:0.8rem;color:rgba(255,255,255,0.5);">ESC para fechar</span>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Crop image modal / lightbox
// ═══════════════════════════════════════════════════════════════════════════════
function openCropModal(cropId, cropIndex) {
    // Remove any existing modal
    const existing = document.getElementById('crop-modal');
    if (existing) existing.remove();

    const imgSrc = `/api/results/crop/${cropId}/image`;

    const overlay = document.createElement('div');
    overlay.id = 'crop-modal';
    overlay.style.cssText = 'position: fixed; inset: 0; background: rgba(0,0,0,0.88); z-index: 500; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div onclick="event.stopPropagation()" style="max-width: 92vw; max-height: 92vh; display: flex; flex-direction: column; align-items: center;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 8px 0; color: #fff;">
                <span style="font-family: var(--font-mono); font-size: 0.85rem; opacity: 0.8;">Crop ${cropIndex}</span>
                <button class="lightbox-close-btn" onclick="document.getElementById('crop-modal').remove()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <img src="${imgSrc}" alt="Crop ${cropIndex}" style="max-width: 90vw; max-height: 82vh; object-fit: contain; border-radius: var(--radius-md); box-shadow: 0 8px 40px rgba(0,0,0,0.5);"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            <div class="embedding-modal-fallback" style="display:none;">
                <span>🐬</span>
                <p>Crop não disponível</p>
            </div>
            <div style="text-align:center;padding:8px 0;">
                <span class="text-muted" style="font-size:0.8rem;color:rgba(255,255,255,0.5);">ESC para fechar</span>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}
