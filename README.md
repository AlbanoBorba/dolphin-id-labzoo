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

> **🤖 IA & Agentes (Spec-Kit)**: O projeto contém contexto estruturado para agentes de codificação. Veja a pasta [`docs/`](./docs/) para arquitetura e prompts de contexto (`AGENTS.md`).

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
├── docs/                   # Documentação do projeto (Spec-Kit)
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

## Métricas de Avaliação

As métricas são avaliadas sob **protocolo honesto sem vazamento de rajada** (galeria histórica $\le 2024$ e consultas reais de $2025$, disjuntas no nível de encontro):

| Métrica | Protocolo Geral (Todas as Formas) | Gate de Nadadeira Padrão (Aspect Ratio 1.5–3.0) | Observação Metodológica |
|:---|:---:|:---:|:---|
| **Top-1 Accuracy** | **68.60%** | **79.65%** | Reconhecimento de indivíduos reavistados na temporada seguinte |
| **Top-5 Accuracy** | **75.62%** | **83.14%** | Chance do indivíduo correto estar no Top-5 sugerido |
| **Top-10 Accuracy** | **78.51%** | **83.72%** | Sugestões apresentadas para triagem do biólogo |
| **mAP** | **59.48%** | **68.31%** | Ordenação global de retrieval |

> **Nota Metodológica (Invariante I-4):**
> - **Escopo:** Subconjunto inequívoco de 60 indivíduos curados, avaliado sobre o split temporal versionado (`splits/temporal_split.parquet`, hash `6a1aed066d437bf6`).
> - *Métricas antigas publicadas (~88,6% Top-1)* mediam auto-recuperação sobre o próprio treino com vazamento de rajada na diagonal. Os números acima refletem a capacidade real de reavistamento entre anos disjuntos.

## Tecnologias

- **Backend**: FastAPI + SQLite + SQLModel
- **Frontend**: HTML/CSS/JS (vanilla)
- **Detecção**: YOLO-World (Zero-Shot)
- **Re-ID**: EfficientNet-B0 + ArcFace + Triplet Loss
- **Matching**: Cosine similarity contra galeria pré-computada
