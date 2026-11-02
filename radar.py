"""Radar do canal - noite 3: multiplicador de outlier (só vídeos longos).

Busca vídeos em português sobre um termo (últimos 6 meses) e compara as views
de cada um com a mediana dos últimos vídeos do próprio canal.
Multiplicador = views do vídeo / mediana do canal. Outlier = 3x ou mais.
Shorts ficam fora, tanto da busca quanto da mediana.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from statistics import median

import requests
from dotenv import load_dotenv

# Lê o arquivo .env e coloca as variáveis dele no ambiente.
load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"

LIMITE_OUTLIER = 3.0       # 3x a mediana do canal
VIDEOS_POR_CANAL = 30      # quantos uploads recentes ler (Shorts são descartados depois)
DURACAO_MINIMA = 180       # segundos; Shorts têm até 3 minutos, então só conta acima disso
DIAS_MINIMOS = 7           # ignora vídeos com menos de 7 dias (ainda estão crescendo)
MINIMO_PARA_MEDIANA = 3    # com menos vídeos que isso, a mediana não é confiável

# Conta o que gastamos de cota em cada execução.
cota = {"buscas": 0, "unidades": 0}


def chamar_api(endpoint, params, opcional=False):
    """Chama um endpoint da API e devolve o JSON.

    Em caso de erro, mostra só a mensagem da API. Não usamos
    raise_for_status() porque ele imprime a URL inteira, com a chave junto.
    Com opcional=True, um erro devolve None em vez de parar o script
    (útil para um canal que não deixa ler a lista de vídeos).
    """
    params = {**params, "key": API_KEY}
    resposta = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)

    if endpoint == "search":
        cota["buscas"] += 1
    else:
        cota["unidades"] += 1

    if resposta.status_code != 200:
        if opcional:
            return None
        erro = resposta.json().get("error", {}).get("message", resposta.text)
        raise SystemExit(f"Erro {resposta.status_code} em {endpoint}: {erro}")
    return resposta.json()


def em_lotes(itens, tamanho=50):
    """Divide uma lista em pedaços de até 50, o máximo que a API aceita por chamada."""
    itens = list(itens)
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio:inicio + tamanho]


def data_de(video):
    """Converte a data de publicação do vídeo (texto ISO) em datetime."""
    return datetime.fromisoformat(video["snippet"]["publishedAt"].replace("Z", "+00:00"))


def views_de(video):
    return int(video["statistics"].get("viewCount", 0))


def segundos_de(video):
    """Converte a duração da API (formato ISO 8601, ex.: PT14M32S) em segundos."""
    texto = video.get("contentDetails", {}).get("duration", "")
    partes = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", texto)
    if not partes:
        return 0  # live em andamento ou formato desconhecido: tratamos como curto
    dias, horas, minutos, segundos = (int(x or 0) for x in partes.groups())
    return ((dias * 24 + horas) * 60 + minutos) * 60 + segundos


def e_longo(video):
    return segundos_de(video) > DURACAO_MINIMA


def buscar_videos(termo, max_resultados=10):
    """Busca vídeos pelo termo (search.list) e devolve só os IDs.

    A busca é a chamada escassa da API, então ela só traz IDs.
    Os números de cada vídeo vêm depois, em chamadas baratas e em lote.
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
    """Título, canal, data e estatísticas de vários vídeos, 50 por chamada."""
    videos = []
    for lote in em_lotes(ids):
        dados = chamar_api("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(lote)})
        videos.extend(dados["items"])
    return videos


def dados_dos_canais(ids_dos_canais):
    """Para cada canal: a playlist de uploads (onde ficam todos os vídeos) e os inscritos."""
    canais = {}
    for lote in em_lotes(ids_dos_canais):
        dados = chamar_api("channels", {"part": "contentDetails,statistics", "id": ",".join(lote)})
        for canal in dados["items"]:
            canais[canal["id"]] = {
                "uploads": canal["contentDetails"]["relatedPlaylists"]["uploads"],
                "inscritos": int(canal["statistics"].get("subscriberCount", 0)),
            }
    return canais


def ultimos_videos(playlist_uploads):
    """IDs dos vídeos mais recentes do canal (1 unidade de cota por canal)."""
    dados = chamar_api("playlistItems", {
        "part": "contentDetails",
        "playlistId": playlist_uploads,
        "maxResults": VIDEOS_POR_CANAL,
    }, opcional=True)
    if not dados:
        return []
    return [item["contentDetails"]["videoId"] for item in dados["items"]]


def medianas_dos_canais(canais):
    """Calcula a mediana de views dos últimos vídeos de cada canal.

    Usamos mediana, não média: um único viral puxa a média para cima
    e esconderia os outros outliers do mesmo canal.
    Ficam de fora: Shorts (fazem bem menos views que os vídeos longos e
    derrubariam a mediana) e vídeos com menos de DIAS_MINIMOS dias, que
    ainda não tiveram tempo de juntar views.
    Devolve, por canal, a mediana e quantos vídeos entraram na conta.
    """
    ids_por_canal = {cid: ultimos_videos(info["uploads"]) for cid, info in canais.items()}
    todos_os_ids = [vid for ids in ids_por_canal.values() for vid in ids]
    por_id = {video["id"]: video for video in detalhes_dos_videos(todos_os_ids)}

    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_MINIMOS)
    medianas = {}
    for cid, ids in ids_por_canal.items():
        views = [views_de(por_id[vid]) for vid in ids
                 if vid in por_id and e_longo(por_id[vid]) and data_de(por_id[vid]) < limite]
        mediana = median(views) if len(views) >= MINIMO_PARA_MEDIANA else None
        medianas[cid] = (mediana, len(views))
    return medianas


def radar(termo, max_resultados=10):
    """Roda o radar para um termo e devolve uma lista de resultados, do maior multiplicador ao menor."""
    encontrados = detalhes_dos_videos(buscar_videos(termo, max_resultados))
    videos = [v for v in encontrados if e_longo(v)]  # Shorts não servem de referência para nós
    canais = dados_dos_canais({v["snippet"]["channelId"] for v in videos})
    medianas = medianas_dos_canais(canais)

    resultados = []
    for v in videos:
        cid = v["snippet"]["channelId"]
        mediana, base = medianas.get(cid, (None, 0))
        views = views_de(v)
        resultados.append({
            "id": v["id"],
            "titulo": v["snippet"]["title"],
            "canal": v["snippet"]["channelTitle"],
            "inscritos": canais.get(cid, {}).get("inscritos", 0),
            "views": views,
            "mediana": mediana,
            "base": base,
            "minutos": round(segundos_de(v) / 60),
            "multiplicador": round(views / mediana, 1) if mediana else None,
            "publicado": data_de(v).date().isoformat(),
        })

    # Quem não tem multiplicador (mediana desconhecida) vai para o fim.
    resultados.sort(key=lambda r: r["multiplicador"] or -1, reverse=True)
    return resultados


def imprimir(resultados):
    print(f"{'':2} {'mult.':>6} | {'views':>9} | {'mediana':>8} | {'base':>4} | {'min':>3} | {'canal':<22} | título")
    for r in resultados:
        marca = "*" if r["multiplicador"] and r["multiplicador"] >= LIMITE_OUTLIER else " "
        mult = f"{r['multiplicador']:.1f}x" if r["multiplicador"] else "  ?"
        mediana = f"{r['mediana']:,.0f}" if r["mediana"] else "?"
        print(f"{marca:2} {mult:>6} | {r['views']:>9,} | {mediana:>8} | {r['base']:>4} | {r['minutos']:>3} | "
              f"{r['canal'][:22]:<22} | {r['titulo'][:60]}")


def main():
    if not API_KEY:
        raise SystemExit("Faltou a YOUTUBE_API_KEY no arquivo .env")

    termo = "engenharia reversa"
    resultados = radar(termo)

    print(f"Termo: {termo}\n")
    imprimir(resultados)
    outliers = sum(1 for r in resultados if r["multiplicador"] and r["multiplicador"] >= LIMITE_OUTLIER)
    print("\nbase = vídeos longos do canal usados na mediana; min = duração do vídeo")
    print(f"* = outlier ({LIMITE_OUTLIER:.0f}x ou mais a mediana do canal): {outliers} de {len(resultados)}")
    print(f"Cota gasta: {cota['buscas']} busca(s) e {cota['unidades']} unidade(s) de leitura")


if __name__ == "__main__":
    main()
