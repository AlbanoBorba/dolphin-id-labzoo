/**
 * DolphinID — Home / Upload page
 *
 * Two input modes:
 *   1. File picker: select multiple images via browser dialog
 *   2. Folder path: type a local path and browse its contents
 */

// State for the upload page
let _uploadState = {
    mode: 'upload',        // 'upload' or 'folder'
    selectedFiles: [],     // File objects from input
    folderPath: '',        // Typed folder path
    folderImages: [],      // Images found in folder (from browse API)
};

async function renderHomePage(container) {
    // Load existing sessions
    let sessions = [];
    try {
        sessions = await apiJson('/api/sessions');
    } catch { /* ignore - first time */ }

    _uploadState = { mode: 'upload', selectedFiles: [], folderPath: '', folderImages: [] };

    const sessionsHtml = sessions.length > 0 ? sessions.map(s => `
        <div class="session-item" onclick="${s.status === 'processing' ? `navigate('#/processing?id=${s.id}')` : s.status === 'completed' ? `navigate('#/results?id=${s.id}')` : ''}">
            <div class="session-info">
                <div class="session-name">${s.name}</div>
                <div class="session-meta">${formatDate(s.created_at)} · ${s.year} · ${s.total_images} imagens</div>
            </div>
            <div class="flex items-center gap-4">
                ${statusBadge(s.status)}
                ${s.status === 'completed' ? `
                    <div class="flex gap-2">
                        <a href="/api/export/${s.id}/csv" class="btn btn-ghost btn-sm" title="Exportar CSV" onclick="event.stopPropagation()">📥 CSV</a>
                        <a href="/api/export/${s.id}/report" target="_blank" class="btn btn-ghost btn-sm" title="Relatório HTML" onclick="event.stopPropagation()">📄 Relatório</a>
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('') : `
        <div class="empty-state" style="padding: 40px 0">
            <div class="empty-state-icon">📂</div>
            <div class="empty-state-text">Nenhuma sessão ainda</div>
            <p class="text-muted">Crie sua primeira sessão de identificação acima.</p>
        </div>
    `;

    container.innerHTML = `
        <div class="page-header">
            <h1 class="page-title">Identificação de Botos</h1>
            <p class="page-subtitle">Submeta imagens para detecção e identificação automática de nadadeiras dorsais.</p>
        </div>

        <div class="card mb-6">
            <div class="card-header">
                <h2>Nova Sessão de Identificação</h2>
                <!-- Mode Toggle -->
                <div class="mode-toggle">
                    <button class="mode-btn active" id="mode-upload-btn" onclick="switchUploadMode('upload')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        Selecionar Arquivos
                    </button>
                    <button class="mode-btn" id="mode-folder-btn" onclick="switchUploadMode('folder')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                        Caminho da Pasta
                    </button>
                </div>
            </div>
            <div class="card-body">
                <!-- Upload Mode: File Picker -->
                <div id="mode-upload-panel">
                    <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()">
                        <input type="file" id="file-input" multiple accept="image/*" style="display:none" onchange="handleFilesSelected(this.files)">
                        <div class="upload-zone-icon">📷</div>
                        <div class="upload-zone-text">Clique para selecionar imagens ou arraste aqui</div>
                        <div class="upload-zone-hint">JPG, PNG, BMP, TIFF · Múltiplos arquivos</div>
                    </div>

                    <!-- Thumbnails preview -->
                    <div id="upload-preview" class="hidden">
                        <div class="preview-header">
                            <span id="preview-count" class="text-muted"></span>
                            <button class="btn btn-ghost btn-sm" onclick="clearSelectedFiles()">Limpar</button>
                        </div>
                        <div class="thumbnail-grid" id="thumbnail-grid"></div>
                    </div>
                </div>

                <!-- Folder Mode: Path Input + Browse -->
                <div id="mode-folder-panel" class="hidden">
                    <div class="form-group">
                        <label class="form-label">
                            📁 Caminho da pasta com imagens
                            <span class="form-label-hint">Caminho completo no computador</span>
                        </label>
                        <div class="input-with-btn">
                            <input type="text" class="form-input" id="source-dir"
                                   placeholder="C:\\fotos\\campo-abril-2026"
                                   onkeydown="if(event.key==='Enter'){event.preventDefault();browseFolderPath();}">
                            <button class="btn btn-secondary" onclick="browseFolderPath()" id="browse-btn">Explorar</button>
                        </div>
                    </div>

                    <!-- Folder contents preview -->
                    <div id="folder-preview" class="hidden">
                        <div class="preview-header">
                            <span id="folder-preview-count" class="text-muted"></span>
                            <button class="btn btn-ghost btn-sm" id="folder-parent-btn" class="hidden" onclick="navigateToParent()">⬆ Pasta Pai</button>
                        </div>

                        <!-- Subdirectories -->
                        <div id="folder-subdirs"></div>

                        <!-- Image thumbnails -->
                        <div class="thumbnail-grid" id="folder-thumbnail-grid"></div>
                    </div>
                </div>

                <!-- Session details (shared by both modes) -->
                <div class="session-details-row mt-4">
                    <div class="form-group" style="flex: 0 0 140px;">
                        <label class="form-label">📅 Ano</label>
                        <input type="number" class="form-input" id="session-year"
                               value="${new Date().getFullYear()}" min="2000" max="2099">
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label class="form-label">📝 Nome / Notas <span class="form-label-hint">(opcional)</span></label>
                        <input type="text" class="form-input" id="session-notes"
                               placeholder="Campo da Tesoura">
                    </div>
                    <div class="form-group" style="flex: 0 0 auto; align-self: flex-end;">
                        <button class="btn btn-primary btn-lg" id="submit-btn" onclick="handleSubmit()" disabled>
                            🔍 Iniciar Processamento
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2>📋 Sessões Anteriores</h2>
                <span class="text-muted" style="font-size: 0.85rem">${sessions.length} sessões</span>
            </div>
            <div class="card-body">
                ${sessionsHtml}
            </div>
        </div>
    `;

    // Setup drag and drop
    setupDragAndDrop();
}


// --- Mode Switching ---

function switchUploadMode(mode) {
    _uploadState.mode = mode;

    document.getElementById('mode-upload-btn').classList.toggle('active', mode === 'upload');
    document.getElementById('mode-folder-btn').classList.toggle('active', mode === 'folder');
    document.getElementById('mode-upload-panel').classList.toggle('hidden', mode !== 'upload');
    document.getElementById('mode-folder-panel').classList.toggle('hidden', mode !== 'folder');

    updateSubmitButton();
}


// --- File Upload Mode ---

function handleFilesSelected(fileList) {
    const files = Array.from(fileList).filter(f =>
        f.type.startsWith('image/') || /\.(jpe?g|png|bmp|tiff?|webp)$/i.test(f.name)
    );

    if (files.length === 0) {
        showToast('Nenhuma imagem encontrada nos arquivos selecionados', 'error');
        return;
    }

    _uploadState.selectedFiles = files;
    renderUploadPreview(files);
    updateSubmitButton();
}

function renderUploadPreview(files) {
    const previewEl = document.getElementById('upload-preview');
    const gridEl = document.getElementById('thumbnail-grid');
    const countEl = document.getElementById('preview-count');

    countEl.textContent = `${files.length} imagem${files.length !== 1 ? 'ns' : ''} selecionada${files.length !== 1 ? 's' : ''}`;
    previewEl.classList.remove('hidden');

    gridEl.innerHTML = '';

    files.forEach((file, i) => {
        const url = URL.createObjectURL(file);
        const card = document.createElement('div');
        card.className = 'thumbnail-card';
        card.innerHTML = `
            <img src="${url}" alt="${file.name}" class="thumbnail-img" loading="lazy"
                 onclick="openLightbox('${url}', '${file.name.replace(/'/g, "\\'")}')" >
            <div class="thumbnail-name" title="${file.name}">${file.name}</div>
            <div class="thumbnail-size">${(file.size / 1024).toFixed(0)} KB</div>
        `;
        gridEl.appendChild(card);
    });

    // Hide the upload zone, show a small "add more" button
    document.getElementById('upload-zone').style.display = 'none';
}

function clearSelectedFiles() {
    _uploadState.selectedFiles = [];
    document.getElementById('upload-preview').classList.add('hidden');
    document.getElementById('thumbnail-grid').innerHTML = '';
    document.getElementById('upload-zone').style.display = '';
    document.getElementById('file-input').value = '';
    updateSubmitButton();
}


// --- Folder Path Mode ---

async function browseFolderPath() {
    const pathInput = document.getElementById('source-dir');
    const path = pathInput.value.trim();

    if (!path) {
        showToast('Informe o caminho da pasta', 'error');
        return;
    }

    const btn = document.getElementById('browse-btn');
    btn.disabled = true;
    btn.textContent = '...';

    try {
        const data = await apiJson(`/api/browse?path=${encodeURIComponent(path)}`);

        _uploadState.folderPath = data.directory;
        _uploadState.folderImages = data.images;
        pathInput.value = data.directory;

        renderFolderPreview(data);
        updateSubmitButton();
    } catch (err) {
        showToast(`Erro: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Explorar';
    }
}

function renderFolderPreview(data) {
    const previewEl = document.getElementById('folder-preview');
    const countEl = document.getElementById('folder-preview-count');
    const subdirsEl = document.getElementById('folder-subdirs');
    const gridEl = document.getElementById('folder-thumbnail-grid');

    previewEl.classList.remove('hidden');
    countEl.textContent = `${data.total_images} imagem${data.total_images !== 1 ? 'ns' : ''} encontrada${data.total_images !== 1 ? 's' : ''}`;

    // Render subdirectories
    if (data.subdirectories && data.subdirectories.length > 0) {
        subdirsEl.innerHTML = `
            <div class="subdirs-row">
                ${data.subdirectories.map(d => `
                    <button class="subdir-chip" onclick="navigateToFolder('${d.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')">
                        📁 ${d.name}
                        <span class="subdir-count">${d.image_count}</span>
                    </button>
                `).join('')}
            </div>
        `;
    } else {
        subdirsEl.innerHTML = '';
    }

    // Render image thumbnails
    gridEl.innerHTML = '';

    if (data.images.length === 0) {
        gridEl.innerHTML = '<div class="text-muted text-center" style="grid-column: 1/-1; padding: 24px;">Nenhuma imagem encontrada nesta pasta</div>';
        return;
    }

    data.images.forEach(img => {
        const thumbUrl = `/api/browse/thumbnail?path=${encodeURIComponent(img.path)}&size=200`;
        const fullUrl = `/api/browse/image?path=${encodeURIComponent(img.path)}`;
        const card = document.createElement('div');
        card.className = 'thumbnail-card';
        card.innerHTML = `
            <img src="${thumbUrl}" alt="${img.name}" class="thumbnail-img" loading="lazy"
                 onclick="openLightbox('${fullUrl}', '${img.name.replace(/'/g, "\\'")}')" >
            <div class="thumbnail-name" title="${img.name}">${img.name}</div>
            <div class="thumbnail-size">${img.size_kb} KB</div>
        `;
        gridEl.appendChild(card);
    });
}

function navigateToFolder(path) {
    document.getElementById('source-dir').value = path;
    browseFolderPath();
}

function navigateToParent() {
    const current = _uploadState.folderPath;
    if (!current) return;

    // Go up one directory
    const parts = current.replace(/\//g, '\\').split('\\');
    parts.pop();
    const parent = parts.join('\\');
    if (parent) {
        document.getElementById('source-dir').value = parent;
        browseFolderPath();
    }
}


// --- Drag & Drop ---

function setupDragAndDrop() {
    const zone = document.getElementById('upload-zone');
    if (!zone) return;

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
    });
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFilesSelected(e.dataTransfer.files);
        }
    });
}


// --- Lightbox ---

function openLightbox(src, title) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.onclick = () => overlay.remove();
    overlay.innerHTML = `
        <div class="lightbox-content" onclick="event.stopPropagation()">
            <div class="lightbox-header">
                <span class="lightbox-title">${title}</span>
                <button class="btn btn-ghost btn-sm" onclick="this.closest('.lightbox-overlay').remove()" style="color:white">✕</button>
            </div>
            <img src="${src}" alt="${title}" class="lightbox-img">
        </div>
    `;
    document.body.appendChild(overlay);
}


// --- Submit ---

function updateSubmitButton() {
    const btn = document.getElementById('submit-btn');
    if (!btn) return;

    if (_uploadState.mode === 'upload') {
        btn.disabled = _uploadState.selectedFiles.length === 0;
    } else {
        btn.disabled = _uploadState.folderImages.length === 0;
    }
}

async function handleSubmit() {
    const year = parseInt(document.getElementById('session-year').value);
    const notes = document.getElementById('session-notes').value.trim();
    const btn = document.getElementById('submit-btn');

    btn.disabled = true;
    btn.textContent = 'Iniciando...';

    try {
        if (_uploadState.mode === 'upload') {
            // Upload files via multipart form
            const formData = new FormData();
            formData.append('year', year);
            if (notes) {
                formData.append('name', notes);
                formData.append('notes', notes);
            }
            for (const file of _uploadState.selectedFiles) {
                formData.append('files', file);
            }

            const response = await fetch('/api/sessions/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `Upload failed: ${response.status}`);
            }

            const session = await response.json();
            showToast(`Sessão criada! Processando ${_uploadState.selectedFiles.length} imagens...`, 'success');
            navigate(`#/processing?id=${session.id}`);

        } else {
            // Folder path mode (original behavior)
            const session = await apiJson('/api/sessions', {
                method: 'POST',
                body: JSON.stringify({
                    source_dir: _uploadState.folderPath,
                    year: year,
                    name: notes || undefined,
                    notes: notes || undefined,
                }),
            });

            showToast(`Sessão criada! Processando ${_uploadState.folderImages.length} imagens...`, 'success');
            navigate(`#/processing?id=${session.id}`);
        }
    } catch (err) {
        showToast(`Erro: ${err.message}`, 'error');
        btn.disabled = false;
        btn.textContent = '🔍 Iniciar Processamento';
    }
}
