# 🎵 ChronoTune

**Organizador Inteligente de Músicas por Ano**

ChronoTune é uma ferramenta Python que organiza automaticamente sua biblioteca de músicas por ano de lançamento, usando metadados dos arquivos e a API do Spotify para identificação precisa.

---

## 🎥 Demonstração

[![Assista no YouTube](https://img.shields.io/badge/▶️_Assista_no_YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/watch?v=1-PtkHM5YI4)

## ✨ Funcionalidades

- 🎯 **Identificação Inteligente**: Usa metadados dos arquivos + API do Spotify para máxima precisão
- 📁 **Organização Automática**: Move músicas para pastas organizadas por ano
- 💾 **Backup Automático**: Cria cópias de segurança antes de mover arquivos
- 🗂️ **Cache Inteligente**: Memoriza identificações para não buscar a mesma música duas vezes
- 🎨 **Interface Visual**: Menu interativo com cores e barra de progresso
- 🎼 **Suporte Multi-formato**: MP3, M4A, MP4, FLAC, WAV, OGG, OPUS, WMA, AAC

---

## 📋 Requisitos

- **Python 3.7+**
- Sistema operacional: Windows, Linux ou macOS

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/chronotune.git
cd chronotune
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

**Dependências instaladas:**
- `mutagen` - Leitura de metadados de áudio
- `spotipy` - Integração com API do Spotify
- `colorama` - Interface colorida no terminal
- `tqdm` - Barras de progresso
- `requests` - Requisições HTTP

---

## 💡 Como Usar

### Modo Interativo (Recomendado)

Execute o programa sem argumentos para usar o menu interativo:

```bash
python chronotube.py
```

O programa vai te guiar através de:
1. **Seleção da pasta** com suas músicas
2. **Escolha dos anos** que deseja filtrar
3. **Opções de backup** e uso do Spotify
4. **Confirmação** antes de executar

### Modo Linha de Comando

Para uso rápido sem interação:

```bash
# Usar pasta atual e anos 2024-2025
python chronotube.py . --years 2024,2025

# Especificar pasta e intervalo de anos
python chronotube.py /caminho/para/musicas --years 2020-2025

# Desabilitar backup e Spotify
python chronotube.py . --years 2024 --no-backup --no-spotify

# Limpar cache antes de executar
python chronotube.py --clear-cache
```

---

## 📂 Como Funciona

### Estrutura de Organização

O ChronoTune organiza suas músicas criando pastas por ano:

```
Sua Pasta de Músicas/
├── 2020/
│   ├── musica1.mp3
│   └── musica2.mp3
├── 2024/
│   ├── musica3.mp3
│   └── musica4.mp3
└── 2025/
    └── musica5.mp3
```

### Sistema de Identificação

O programa usa uma hierarquia de métodos para identificar o ano:

1. **Cache** - Verifica se já identificou esse arquivo antes
2. **Metadados do Arquivo** - Lê tags ID3, MP4, FLAC, etc.
3. **API do Spotify** - Busca informações online (se habilitado)
4. **Nome do Arquivo** - Analisa padrões no nome (ex: "musica_2024.mp3")

### Backup de Segurança

Quando ativado (padrão), o programa cria uma pasta `backup_musicas/` com cópias de todos os arquivos antes de movê-los.

---

## 🔧 Configuração do Spotify

O ChronoTune vem com credenciais públicas do Spotify já configuradas. Para usar suas próprias credenciais:

1. Acesse [Spotify for Developers](https://developer.spotify.com/dashboard)
2. Crie um novo aplicativo
3. Copie o **Client ID** e **Client Secret**
4. Edite o arquivo `chronotube.py`:

```python
SPOTIFY_CLIENT_ID = "seu_client_id_aqui"
SPOTIFY_CLIENT_SECRET = "seu_client_secret_aqui"
```

---

## 🐛 Problemas Comuns

### "ModuleNotFoundError"

Execute: `pip install -r requirements.txt`

### "Spotify API desabilitado"

Isso é normal se não houver internet. O programa continua funcionando com metadados locais.

### Músicas não sendo identificadas

1. Tente limpar o cache: `python chronotube.py --clear-cache`
2. Verifique se os arquivos têm metadados corretos
3. Habilite o Spotify para melhor precisão

---

## 👨‍💻 Autor

[![GitHub](https://img.shields.io/badge/GitHub-lucasgabriel--fiap-181717?style=flat&logo=github)](https://github.com/lucasgabriel-fiap)

---

## 🌟 Dê uma estrela!

Se este projeto foi útil para você, considere dar uma ⭐ no repositório!
