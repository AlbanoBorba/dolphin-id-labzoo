/**
 * DolphinID — Processing progress page
 */

let _processingInterval = null;

async function renderProcessingPage(container, params) {
    const sessionId = params.get('id');
    if (!sessionId) {
        navigate('#/');
        return;
    }

    container.innerHTML = `
        <div class="page-header">
            <h1 class="page-title">Processando...</h1>
            <p class="page-subtitle">YOLO-World está detectando nadadeiras e o modelo está identificando indivíduos.</p>
        </div>

        <div class="card">
            <div class="card-body" style="padding: 40px;">
                <div id="progress-content">
                    <div class="loading-screen">
                        <div class="loading-spinner"></div>
                        <p>Carregando status...</p>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Start polling
    await updateProgress(sessionId);
    _processingInterval = setInterval(() => updateProgress(sessionId), 1500);
}

async function updateProgress(sessionId) {
    try {
        const progress = await apiJson(`/api/sessions/${sessionId}`);
        const el = document.getElementById('progress-content');
        if (!el) {
            clearInterval(_processingInterval);
            return;
        }

        const percent = progress.progress_percent || 0;
        const breakdown = progress.status_breakdown || {};

        if (progress.status === 'completed' || progress.status === 'failed') {
            clearInterval(_processingInterval);

            if (progress.status === 'completed') {
                el.innerHTML = `
                    <div style="text-align: center;">
                        <div style="font-size: 4rem; margin-bottom: 16px;">✅</div>
                        <h2 style="margin-bottom: 8px; color: var(--seafoam);">Processamento Concluído!</h2>
                        <p class="text-muted mb-6">
                            ${progress.processed_images} imagens processadas
                            ${progress.failed_images > 0 ? ` · ${progress.failed_images} falharam` : ''}
                        </p>

                        <div class="grid-stats" style="max-width: 500px; margin: 0 auto 32px;">
                            ${Object.entries(breakdown).map(([status, count]) => `
                                <div class="stat-card">
                                    <div class="stat-number">${count}</div>
                                    <div class="stat-label">${status}</div>
                                </div>
                            `).join('')}
                        </div>

                        <button class="btn btn-primary btn-lg" onclick="navigate('#/results?id=${sessionId}')">
                            📊 Ver Resultados
                        </button>
                    </div>
                `;
                showToast('Processamento concluído!', 'success');
                updateSystemStatus();
            } else {
                el.innerHTML = `
                    <div style="text-align: center;">
                        <div style="font-size: 4rem; margin-bottom: 16px;">❌</div>
                        <h2 style="color: var(--status-failed);">Processamento Falhou</h2>
                        <p class="text-muted mt-4 mb-6">Verifique os logs do servidor para mais detalhes.</p>
                        <button class="btn btn-primary" onclick="navigate('#/')">Voltar ao Início</button>
                    </div>
                `;
                showToast('Processamento falhou!', 'error');
            }
            return;
        }

        // Processing in progress
        el.innerHTML = `
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="text-align: center; margin-bottom: 32px;">
                    <div style="font-size: 3rem; margin-bottom: 8px;">🔍</div>
                    <h2>Processando imagens...</h2>
                </div>

                <div class="progress-bar" style="height: 14px; margin-bottom: 16px;">
                    <div class="progress-fill" style="width: ${percent}%"></div>
                </div>

                <div style="display: flex; justify-content: space-between; margin-bottom: 32px;">
                    <span class="text-muted">${progress.processed_images} / ${progress.total_images} imagens</span>
                    <span style="font-weight: 700; color: var(--ocean-deep);">${percent.toFixed(0)}%</span>
                </div>

                ${Object.keys(breakdown).length > 0 ? `
                    <div class="grid-stats">
                        ${Object.entries(breakdown).map(([status, count]) => `
                            <div class="stat-card">
                                <div class="stat-number">${count}</div>
                                <div class="stat-label">${status}</div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                ${progress.failed_images > 0 ? `
                    <p style="color: var(--status-failed); font-size: 0.85rem; text-align: center;">
                        ⚠️ ${progress.failed_images} imagens falharam durante o processamento
                    </p>
                ` : ''}
            </div>
        `;
    } catch (err) {
        console.error('Progress update error:', err);
    }
}

// Clean up interval when navigating away
window.addEventListener('hashchange', () => {
    if (_processingInterval) {
        clearInterval(_processingInterval);
        _processingInterval = null;
    }
});
