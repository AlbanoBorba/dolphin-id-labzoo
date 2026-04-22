# Instruções para Agentes de IA e Devs (Spec-Kit)

Este arquivo contém o contexto fundamental sobre o **DolphinID**, focado em orientar agentes autônomos de codificação (como Gemini, Copilot, etc.) ou novos desenvolvedores na manutenção e evolução da base de código.

## 🎯 Objetivo do Projeto

O DolphinID é uma aplicação desktop local com interface web projetada para realizar a foto-identificação de botos-pescadores (*Tursiops truncatus*). A identificação ocorre baseada no formato único e nas marcas das nadadeiras dorsais (dorsal fins). 

O usuário fornece um diretório com fotos de campo, e a aplicação automatiza:
1. A **detecção e corte (crop)** das nadadeiras nas fotos.
2. A **extração de características (embeddings)** usando um modelo de Deep Learning.
3. A **busca e comparação (matching)** contra uma galeria previamente conhecida de botos.
4. A exibição interativa (Top-5 matches) permitindo a confirmação ou recusa das identificações por humanos.

## 🛠 Stack Tecnológica

O projeto adota uma stack focada em Python, ML e uma interface Web limpa:

- **Backend:** FastAPI (Roteamento assíncrono), Uvicorn (Servidor).
- **Banco de Dados Local:** SQLite via SQLModel / SQLAlchemy (Para salvar histórico, sessões, e validações manuais).
- **Gerenciamento de Pacotes:** `uv` (rápido e determinístico, configurado via `pyproject.toml`).
- **Machine Learning / Visão Computacional:**
  - `PyTorch` & `PyTorch Lightning` (Modelagem base).
  - `ultralytics` / YOLO-World (Para detecção Zero-Shot e crop da nadadeira).
  - `timm` (EfficientNet-B0 como backbone para Re-ID).
  - ArcFace Loss (Treinado previamente para extrair os embeddings representativos).
  - `scikit-learn` & `umap-learn` (Para cálculo de Cosine Similarity e projeção em espaço latente).
- **Frontend:** Vanilla HTML / CSS / Javascript. Hospedado nos diretórios estáticos do FastAPI usando templates com `Jinja2`.

## 📂 Estrutura e Navegação de Diretórios

```text
dolphin-id/
├── app/                    # Lógica do Backend FastAPI
│   ├── main.py             # Instância do App FastAPI e montagem de pastas.
│   ├── routers/            # Endpoints REST (Upload, Processamento, Resultados).
│   ├── services/           # Regras de Negócio, chamada para inferência de ML e Banco de Dados.
│   ├── models/             # Schemas Pydantic / SQLModel (Tipagem de dados).
│   └── static/             # Assets Web (JS, CSS) e templates HTML (Jinja2).
├── ml/                     # Módulos de PyTorch Lightning carregados dinamicamente para inferência.
├── scripts/                # Scripts utilitários de setup (ex: copiar pesos do modelo).
├── data/                   # (Gerado em Runtime) Onde salvamos os SQLite, as fotos com crops, e baixamos pesos.
├── tests/                  # Suíte de testes Pytest (Unitários e de Integração).
├── pyproject.toml          # Configuração do Python via `uv`.
└── run.py                  # Script unificado para inicialização do Uvicorn.
```

## 📜 Regras de Desenvolvimento

1. **Idiomas:** 
   - A interface do usuário (UI) e a documentação principal estão em **Português**. 
   - Código, variáveis, endpoints REST e funções em **Inglês** (Padrão de mercado).
   - *Docstrings* preferencialmente em Português ou Inglês (mas mantenha um padrão coeso no arquivo editado).
2. **Tipagem (Type Hinting):** Obrigatório o uso rigoroso de Type Hints nativos do Python 3.10+ (ex: `list[str]`, `str | None`).
3. **Padrão de Arquitetura:** O `router` apenas recebe requisições e retorna respostas HTTP. Qualquer lógica complexa de negócios, processamento de imagem ou acesso ao banco DEVE ser delegada a arquivos em `app/services/`.
4. **Dependências:** Não adicione dependências com `pip install`. Para adicionar novas bibliotecas, edite o `pyproject.toml` ou use o comando apropriado do `uv` (ex: `uv add nome_do_pacote`).
5. **Modelos Locais:** A inferência ocorre localmente (não fazemos API requests para nuvem para a predição). Toda a inferência de ML usa os pacotes `ml/` e carrega arquivos `.pt` ou `.ckpt` previamente treinados que residem na pasta `data/models/`.

## 🧪 Testes Automatizados

O projeto utiliza **pytest**. 
- Sempre escreva ou atualize os testes na pasta `tests/` ao adicionar ou alterar lógicas. 
- Utilize o cliente de teste do FastAPI (`TestClient` via `httpx`) para validar rotas em `tests/integration/`.
- Mocke operações demoradas (como inferência YOLO ou EfficientNet) em testes unitários.

Comando para rodar:
```bash
uv run pytest
```
