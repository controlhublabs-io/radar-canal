# radar-canal

Radar de temas para o canal: busca vídeos no YouTube, calcula quanto cada um
performou acima da média do próprio canal e grava os outliers (3x ou mais)
na base "Ideias de vídeo" do Notion.

## Como rodar

1. Crie o ambiente virtual e instale as dependências:

   ```bash
   python -m venv .venv
   # Windows:   .venv\Scripts\activate
   # Linux/Mac: source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e coloque a sua chave da API do YouTube.
   O `.env` nunca vai para o Git (está no `.gitignore`).

3. Rode:

   ```bash
   python radar.py
   ```

## Cota da API

A busca (`search.list`) é a chamada escassa. Leituras de vídeos e canais
(`videos.list`, `channels.list`) são baratas e aceitam até 50 IDs por chamada.
Por isso o radar faz poucas buscas e muitas leituras em lote.

## Andamento

- [x] Noite 1: chave da API criada e testada
- [x] Noite 2: primeira busca (`radar.py`)
- [x] Noite 3: mediana do canal e multiplicador de outlier
- [ ] Noite 4: gravar no Notion sem duplicar
- [ ] Noite 5: palavras-chave das 20 ideias, filtros e controle de cota
- [ ] Noite 6: execução semanal com GitHub Actions
