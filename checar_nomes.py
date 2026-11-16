"""Checa nomes de canal antes de investir em marca.

Para cada nome de nomes_canal.txt:
1. Busca canais com nome parecido (1 busca por nome).
2. Confere se os identificadores @nome, @nomegames, @nomebr e @nometv
   já existem (channels.list com forHandle, 1 unidade cada).
3. Dá um veredito: LIVRE, CUIDADO ou OCUPADO.

Uso: python checar_nomes.py [arquivo.txt]   (padrão: nomes_canal.txt)
Custo: 1 busca + cerca de 5 leituras por nome.
"""
import sys
import unicodedata

import radar

SUFIXOS = ["", "games", "br", "tv"]
CANAL_RELEVANTE = 1_000  # canal parecido com mais inscritos que isso já atrapalha


def slug(texto):
    """'Rolê Aberto' -> 'roleaberto' (sem acento, sem espaço, minúsculo)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.lower() if c.isalnum())


def handle_existe(handle):
    """True se @handle já pertence a um canal."""
    dados = radar.chamar_api("channels", {"part": "id", "forHandle": "@" + handle}, opcional=True)
    return bool(dados and dados.get("items"))


def canais_parecidos(nome):
    """Canais cujo título contém o nome (sem acento e espaço), com inscritos."""
    busca = radar.chamar_api("search", {
        "part": "snippet", "q": nome, "type": "channel", "maxResults": 10, "regionCode": "BR",
    })
    ids = [item["id"]["channelId"] for item in busca.get("items", [])]
    if not ids:
        return []
    dados = radar.chamar_api("channels", {"part": "snippet,statistics", "id": ",".join(ids)})
    alvo = slug(nome)
    parecidos = []
    for canal in dados.get("items", []):
        titulo = canal["snippet"]["title"]
        if alvo in slug(titulo):
            inscritos = int(canal["statistics"].get("subscriberCount", 0))
            parecidos.append((titulo, inscritos))
    return sorted(parecidos, key=lambda p: p[1], reverse=True)


def veredito(parecidos, base_livre):
    grandes = [p for p in parecidos if p[1] >= CANAL_RELEVANTE]
    if grandes or not base_livre:
        return "OCUPADO" if grandes else "CUIDADO"
    return "CUIDADO" if parecidos else "LIVRE"


def main():
    if not radar.API_KEY:
        raise SystemExit("Faltou a YOUTUBE_API_KEY no arquivo .env")
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "nomes_canal.txt"
    with open(arquivo, encoding="utf-8") as f:
        nomes = [linha.strip() for linha in f if linha.strip() and not linha.startswith("#")]

    resultados = []
    for nome in nomes:
        print(f"  checando {nome} ...", file=sys.stderr)
        base = slug(nome)
        handles = {base + s: handle_existe(base + s) for s in SUFIXOS}
        parecidos = canais_parecidos(nome)
        resultados.append((nome, veredito(parecidos, not handles[base]), handles, parecidos))

    ordem = {"LIVRE": 0, "CUIDADO": 1, "OCUPADO": 2}
    resultados.sort(key=lambda r: ordem[r[1]])
    print(f"\n{'nome':<22} | {'veredito':<8} | {'@ livres':<38} | maior canal parecido")
    for nome, v, handles, parecidos in resultados:
        livres = ", ".join("@" + h for h, existe in handles.items() if not existe) or "nenhum"
        maior = f"{parecidos[0][0][:28]} ({parecidos[0][1]:,})" if parecidos else "-"
        print(f"{nome[:22]:<22} | {v:<8} | {livres[:38]:<38} | {maior}")

    print("\nLIVRE = @nome livre e nenhum canal com nome igual; CUIDADO = existe canal pequeno parecido ou o @nome base está tomado;")
    print(f"OCUPADO = já existe canal parecido com mais de {CANAL_RELEVANTE:,} inscritos.")
    print("Instagram e TikTok não têm API aberta: confira os 3 primeiros à mão.")
    print(f"Cota gasta: {radar.cota['buscas']} busca(s) e {radar.cota['unidades']} unidade(s) de leitura")


if __name__ == "__main__":
    main()
