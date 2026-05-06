# Guia de Configuração: Computador do Laboratório (DolphinID)

Este guia descreve os passos necessários para configurar o ambiente do DolphinID do zero em um novo computador (como o do laboratório) e como integrar com o catálogo hospedado no OneDrive.

---

## 1. Artefatos e Arquivos Necessários para Transferência

Para o sistema funcionar, a extração de características e a detecção de nadadeiras necessitam de três artefatos principais que **não estão no repositório do GitHub** (pois são arquivos pesados). 

Você precisará copiá-los do seu computador atual (provavelmente de onde treinou o modelo) e transferi-los (via pen-drive, HD externo ou nuvem temporária) para o computador do laboratório:

1. **Modelo Re-ID (PyTorch Lightning Checkpoint):** `best_model_overall.ckpt`
2. **Pesos YOLO-World (Detecção):** `yolov8x-worldv2.pt`
3. **Galeria Pre-computada (PKL):** `dolphin_gallery.pkl`

Esses arquivos geralmente ficam no seu computador em `data/models/` e `data/gallery/` ou nos resultados do CLI de treinamento (`train-model-cli/experiments/...`).

---

## 2. Lidando com o Catálogo Completo (Integração com o OneDrive)

Como o catálogo classificado completo é grande e está hospedado no OneDrive, a melhor e mais fácil solução para manter a aplicação do laboratório conectada a ele **sem perder a sincronização** é usar o **aplicativo desktop do OneDrive para Windows** no computador do laboratório.

### Como fazer:
1. **Sincronize a pasta:** Instale e faça login no OneDrive no computador do laboratório. Selecione a pasta raiz da sua pesquisa (`reId-scripts`, `train-model-cli` ou especificamente a pasta de catálogo que a galeria mapeia) para sincronizar.
2. **Manter Sempre Neste Dispositivo (Recomendado):** O Windows, por padrão, usa "Arquivos Sob Demanda" (só baixa quando você abre o arquivo). Para evitar travamentos e latência enquanto a aplicação roda localmente, clique com o **botão direito** na pasta sincronizada do catálogo e selecione **"Manter sempre neste dispositivo" (Always keep on this device)**. O ícone mudará para um círculo verde sólido, indicando que todos os arquivos foram baixados e estão sempre disponíveis offline.

---

## 3. Passo a Passo do Setup Inicial

Com os arquivos transferidos e o OneDrive configurado, siga o passo a passo abaixo no computador do laboratório:

### Passo 1: Clonar e Instalar Dependências
Abra o terminal (PowerShell) e execute:
```powershell
# Clone o repositório
git clone <URL_DO_GITHUB_DOLPHIN_ID>
cd dolphin-id

# Sincronize/instale os pacotes utilizando o uv
uv sync
```

### Passo 2: Alocar os Artefatos
Crie as pastas necessárias e mova os arquivos que você trouxe no pen-drive/HD externo:

```text
dolphin-id/
└── data/
    ├── models/
    │   ├── best_model_overall.ckpt
    │   └── yolov8x-worldv2.pt
    └── gallery/
        └── dolphin_gallery.pkl
```

### Passo 3: Configurar o Caminho do OneDrive (Arquivo `.env`)
*(Nota: Acabei de adicionar suporte nativo a leitura de arquivos `.env` no projeto para facilitar esse passo!)*

Crie um arquivo chamado **`.env`** (exatamente esse nome, com ponto no início) na pasta raiz `dolphin-id` e coloque o caminho para a sua pasta sincronizada do OneDrive. O caminho deve ser a pasta base usada quando você gerou a galeria (geralmente a raiz do `train-model-cli`):

```env
# Exemplo: Substitua <SeuUsuario> pelo seu nome de usuário no Windows do Laboratório
DOLPHIN_ID_GALLERY_BASE_PATH="C:\Users\<SeuUsuario>\OneDrive\Documentos\Projeto Udesc\pesquisa\reId-scripts\train-model-cli"
```
*A aplicação vai combinar o caminho do `.env` com os caminhos relativos de cada foto guardados no arquivo `.pkl` para exibir as imagens na Galeria.*

### Passo 4: Rodar o Aplicativo
Execute o servidor:
```powershell
uv run python run.py
```
Acesse no navegador: `http://127.0.0.1:8000`

Se a galeria não carregar as imagens, verifique se o caminho em `DOLPHIN_ID_GALLERY_BASE_PATH` está apontando exatamente para o diretório "pai" em que as imagens referenciadas pelo `.pkl` se encontram.
