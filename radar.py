"""Radar do canal - noite 2: primeira busca na API do YouTube.

Busca vídeos em português sobre um termo, publicados nos últimos 6 meses,
e imprime views, canal e título, do mais visto para o menos visto.
"""
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

# Lê o arquivo .env e coloca as variáveis dele no ambiente.
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"


def chamar_api(endpoint, params):
    """Chama um endpoint da API e devolve o JSON.

    Em caso de erro, mostra só a mensagem da API. Não usamos
    raise_for_status() porque ele imprime a URL inteira, com a chave junto.
    """
    params = {**params, "key": API_KEY}
    resposta = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    if resposta.status_code != 200:
        erro = resposta.json().get("error", {}).get("message", resposta.text)
        raise SystemExit(f"Erro {resposta.status_code} em {endpoint}: {erro}")
    return resposta.json()


def buscar_videos(termo, max_resultados=10):
    """Busca vídeos pelo termo (search.list) e devolve só os IDs.

    A busca é a chamada cara da API, então ela só traz IDs.
    Os números de cada vídeo vêm depois, numa chamada barata.
    """
    seis_meses_atras = datetime.now(timezone.utc) - timedelta(days=180)
    dados = chamar_api("search", {
        "part": "snippet",
        "q": termo,
        "type": "video",
        "maxResults": max_resultados,
        "regionCode": "BR",
        "relevanceLanguage": "pt",
        "publishedAfter": seis_meses_atras.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    return [item["id"]["videoId"] for item in dados["items"]]


def detalhes_dos_videos(ids):
    """Pega título, canal e estatísticas de até 50 vídeos numa chamada só."""
    dados = chamar_api("videos", {
        "part": "snippet,statistics",
        "id": ",".join(ids),
    })
    return dados["items"]


def main():
    if not API_KEY:
        raise SystemExit("Faltou a YOUTUBE_API_KEY no arquivo .env")

    ids = buscar_videos("engenharia reversa")
    videos = detalhes_dos_videos(ids)

    # Ordena do mais visto para o menos visto.
    videos.sort(key=lambda v: int(v["statistics"].get("viewCount", 0)), reverse=True)

    for v in videos:
        views = int(v["statistics"].get("viewCount", 0))
        canal = v["snippet"]["channelTitle"][:25]
        titulo = v["snippet"]["title"][:70]
        print(f"{views:>10,} | {canal:<25} | {titulo}")


if __name__ == "__main__":
    main()
