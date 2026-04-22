/**
 * DolphinID — Results / Review page
 */

async function renderResultsPage(container, params) {
    const sessionId = params.get('id');
    if (!sessionId) {
        navigate('#/');
        return;
    }

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

        const results = data.results || [];
        const identified = results.filter(r => r.status === 'identified' || r.status === 'confirmed');
        const noDetect = results.filter(r => r.status === 'no_detection');
        const failed = results.filter(r => r.status === 'failed');
        const confirmed = results.filter(r => r.status === 'confirmed');

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
                    <div class="stat-number" style="color: var(--status-identified)">${identified.length}</div>
                    <div class="stat-label">Identificadas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-confirmed)">${confirmed.length}</div>
                    <div class="stat-label">Confirmadas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-no-detection)">${noDetect.length}</div>
                    <div class="stat-label">Sem Detecção</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: var(--status-failed)">${failed.length}</div>
                    <div class="stat-label">Falharam</div>
                </div>
            </div>

            <!-- Filters -->
            <div class="card mb-6">
                <div class="card-body" style="padding: 12px 20px;">
                    <div class="flex items-center gap-4">
                        <label class="form-label" style="margin: 0; white-space: nowrap;">Filtrar:</label>
                        <select class="form-select" id="filter-status" onchange="filterResults(${sessionId})" style="width: auto; min-width: 160px;">
                            <option value="">Todos</option>
                            <option value="identified">Identificados</option>
                            <option value="confirmed">Confirmados</option>
                            <option value="no_detection">Sem Detecção</option>
                            <option value="failed">Falharam</option>
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

function renderResultsList(results) {
    if (results.length === 0) {
        return `<div class="empty-state"><div class="empty-state-text">Nenhum resultado encontrado</div></div>`;
    }

    return results.map(r => {
        const matches = r.top5_matches || [];
        const finalId = r.confirmed_id || r.predicted_id;
        const confidence = r.match_confidence;

        const matchesHtml = matches.map((m, i) => `
            <span class="match-chip ${i === 0 ? 'best' : ''}" 
                  onclick="confirmResult(${r.id}, '${m.id}')" 
                  title="Clique para confirmar como ${m.id}">
                ${m.id} <span class="match-score">${(m.score * 100).toFixed(0)}%</span>
            </span>
        `).join('');

        const cropSrc = r.crop_path ? `/api/results/${r.id}/crop` : '';

        return `
            <div class="result-card" id="result-${r.id}">
                <div class="result-crop-container">
                    ${cropSrc ? `<img class="result-crop-img" src="${cropSrc}" alt="Crop" loading="lazy">` :
                    `<div class="result-crop-img" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted)">Sem crop</div>`}
                    <span class="font-mono" style="font-size: 0.75rem; color: var(--text-muted); word-break: break-all;">${r.original_filename}</span>
                </div>
                <div class="result-info">
                    <div class="flex items-center justify-between">
                        <div class="result-prediction">
                            ${finalId ? `<span class="result-id">${finalId}</span>` : '<span class="text-muted">—</span>'}
                            ${confidence ? `<span class="result-confidence ${confidenceClass(confidence)}">${(confidence * 100).toFixed(0)}%</span>` : ''}
                        </div>
                        ${statusBadge(r.status)}
                    </div>

                    ${matches.length > 0 ? `
                        <div>
                            <div class="text-muted" style="font-size: 0.8rem; margin-bottom: 4px;">Top-5 Matches (clique para confirmar):</div>
                            <div class="matches-row">${matchesHtml}</div>
                        </div>
                    ` : ''}

                    <div class="actions-row">
                        ${r.status !== 'confirmed' && finalId ? `
                            <button class="btn btn-success btn-sm" onclick="confirmResult(${r.id}, '${finalId}')">
                                ✅ Confirmar ${finalId}
                            </button>
                        ` : ''}
                        ${r.status === 'confirmed' ? `
                            <span style="color: var(--status-confirmed); font-size: 0.85rem; font-weight: 600;">
                                ✅ Confirmado como ${r.confirmed_id}
                            </span>
                        ` : ''}
                        ${r.status !== 'confirmed' ? `
                            <button class="btn btn-ghost btn-sm" onclick="showCustomConfirm(${r.id})">
                                🔄 Outro ID...
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

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

async function confirmResult(resultId, confirmedId) {
    try {
        await apiJson(`/api/results/${resultId}/confirm`, {
            method: 'POST',
            body: JSON.stringify({ confirmed_id: confirmedId }),
        });

        // Update the card in-place
        const card = document.getElementById(`result-${resultId}`);
        if (card) {
            const actionsRow = card.querySelector('.actions-row');
            if (actionsRow) {
                actionsRow.innerHTML = `
                    <span style="color: var(--status-confirmed); font-size: 0.85rem; font-weight: 600;">
                        ✅ Confirmado como ${confirmedId}
                    </span>
                `;
            }
            // Update badge
            const badge = card.querySelector('.badge');
            if (badge) {
                badge.className = 'badge badge-confirmed';
                badge.textContent = 'Confirmado';
            }
        }

        showToast(`Confirmado como ${confirmedId}`, 'success');
    } catch (err) {
        showToast('Erro ao confirmar: ' + err.message, 'error');
    }
}

function showCustomConfirm(resultId) {
    const customId = prompt('Digite o ID correto do indivíduo (ex: #5):');
    if (customId && customId.trim()) {
        confirmResult(resultId, customId.trim());
    }
}
