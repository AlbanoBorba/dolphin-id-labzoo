# DolphinID 🐬

**Ferramenta de identificação automática de botos-pescadores (*Tursiops truncatus*) via foto-identificação de nadadeira dorsal.**

Aplicação desktop local que roda a pipeline de detecção (YOLO-World) e re-identificação (EfficientNet + ArcFace) de maneira acessível, com interface web para revisão dos resultados.

## Funcionalidades

- **Frontend**: Interface web rica estilo Single Page Application (SPA)
- **Modelagem**: Extração de embeddings via ArcFace (PyTorch)
- **Detecção**: Crop automático de nadadeiras via YOLOv8
- **Busca por Similaridade**: Identificação rápida (1-N) utilizando similaridade de cossenos
- **Revisão Visual**: Veja os resultados com Top-5 matches e confirme/corrija as identificações
- **Explorador de Galeria**: Navegue pelos indivíduos conhecidos e suas fotos de referência
- **Espaço Latente**: Visualização interativa 2D do mapa de embeddings com UMAP e Plotly.js
- **Exportação**: Relatórios em CSV e HTML

## Pré-requisitos

- Python 3.10+
- GPU NVIDIA com ~4GB VRAM (funciona também em CPU, mais lento)
- [uv](https://docs.astral.sh/uv/) instalado

## Setup

### 1. Instalar dependências

```bash
cd dolphin-id
uv sync
```

### 2. Copiar artefatos de ML

Os artefatos (modelo treinado, galeria, pesos YOLO) precisam ser copiados do diretório de treino:

```bash
uv run python scripts/setup_artifacts.py --source ../reId-scripts/train-model-cli
```

Isso copia:
- `best_model_overall.ckpt` → `data/models/`
- `dolphin_gallery.pkl` → `data/gallery/`
- `yolov8x-worldv2.pt` → `data/models/`

### 3. Rodar

```bash
uv run python run.py
```

### 4. Acessar
Abra o navegador em `http://127.0.0.1:8000`

## Uso

1. **Início**: Informe o caminho de uma pasta com fotos e inicie o processamento
2. **Processamento**: Acompanhe o progresso em tempo real
3. **Resultados**: Revise as identificações, confirme ou corrija
4. **Galeria**: Navegue pelos indivíduos conhecidos
5. **Espaço Latente**: Visualize os clusters de embeddings

## Estrutura

```
dolphin-id/
├── app/                    # Aplicação FastAPI
│   ├── main.py            # Entry point
│   ├── config.py          # Configuração
│   ├── database.py        # SQLite
│   ├── models/            # Schemas de dados
│   ├── services/          # Lógica de negócio (detecção, identificação, pipeline)
│   ├── routers/           # Endpoints da API
│   └── static/            # Frontend (HTML/CSS/JS)
├── ml/                    # Código de ML (backbone, Lightning module)
├── scripts/               # Scripts de setup
├── data/                  # Dados locais (criado automaticamente)
│   ├── models/            # Checkpoints e pesos 
│   ├── gallery/           # Gallery PKL
│   ├── crops/             # Crops gerados
│   └── db/                # Banco SQLite
├── pyproject.toml         # Dependências (uv)
└── run.py                 # Launcher
```

## Métricas do Modelo

| Métrica | Valor |
|:---|:---:|
| Top-1 Accuracy | 88.59% |
| Top-5 Accuracy | 92.06% |
| mAP | 86.98% |

## Tecnologias

- **Backend**: FastAPI + SQLite + SQLModel
- **Frontend**: HTML/CSS/JS (vanilla)
- **Detecção**: YOLO-World (Zero-Shot)
- **Re-ID**: EfficientNet-B0 + ArcFace + Triplet Loss
- **Matching**: Cosine similarity contra galeria pré-computada
