"""Comparador de nichos: roda o radar para vários termos e resume por nicho.

Lê os nichos e termos de nichos.json, roda o radar em cada termo
(25 vídeos longos por busca) e mostra, por nicho:
- quantos vídeos são outliers (3x ou mais a mediana do próprio canal);
- o multiplicador típico (mediana);
- em quantos canais diferentes os outliers aparecem (concentração);
- quantos outliers vêm de canais pequenos (até 50 mil inscritos),
  que é o sinal de que um canal novo também consegue crescer ali.

Também salva todos os vídeos em resultados_<nome do arquivo>.csv.
Custo aproximado: 1 busca e 25 a 35 leituras por termo.
"""
import csv
import json
import sys
from pathlib import Path
from statistics import median

import radar

CANAL_PEQUENO = 50_000


def resumir(resultados):
    """Resume os vídeos de um termo ou de um nicho inteiro."""
    medidos = [r for r in resultados if r["multiplicador"] is not None]
    outliers = [r for r in medidos if r["multiplicador"] >= radar.LIMITE_OUTLIER]
    return {
        "videos": len(resultados),
        "medidos": len(medidos),
        "outliers": len(outliers),
        "taxa": len(outliers) / len(medidos) if medidos else 0,
        "mult_tipico": median(r["multiplicador"] for r in medidos) if medidos else 0,
        "canais_outlier": len({r["canal"] for r in outliers}),
        "outliers_pequenos": sum(1 for r in outliers if r["inscritos"] <= CANAL_PEQUENO),
    }


def main():
    if not radar.API_KEY:
        raise SystemExit("Faltou a YOUTUBE_API_KEY no arquivo .env")

    # Uso: python comparar_nichos.py [arquivo.json]  (padrão: nichos.json)
    arquivo_nichos = sys.argv[1] if len(sys.argv) > 1 else "nichos.json"
    arquivo_csv = "resultados_" + Path(arquivo_nichos).stem + ".csv"

    with open(arquivo_nichos, encoding="utf-8") as arquivo:
        nichos = json.load(arquivo)

    total_termos = sum(len(termos) for termos in nichos.values())
    print(f"{len(nichos)} nichos, {total_termos} termos. Isso leva alguns minutos.\n")

    linhas_csv = []
    resumo_por_nicho = {}
    vistos = set()  # o mesmo vídeo pode aparecer em dois termos; conta uma vez por nicho

    for nicho, termos in nichos.items():
        do_nicho = []
        for termo in termos:
            print(f"  {nicho} | {termo} ...", file=sys.stderr)
            for r in radar.radar(termo, max_resultados=25):
                linhas_csv.append({"nicho": nicho, "termo": termo, **r})
                if (nicho, r["id"]) not in vistos:
                    vistos.add((nicho, r["id"]))
                    do_nicho.append(r)
        resumo_por_nicho[nicho] = resumir(do_nicho)

    ordem = sorted(resumo_por_nicho.items(), key=lambda item: item[1]["taxa"], reverse=True)
    print(f"\n{'nicho':<38} | {'outl.':>5} | {'taxa':>5} | {'mult.':>5} | {'canais':>6} | {'peq.':>4}")
    for nicho, s in ordem:
        print(f"{nicho[:38]:<38} | {s['outliers']:>2}/{s['medidos']:<2} | {s['taxa']:>5.0%} | "
              f"{s['mult_tipico']:>4.1f}x | {s['canais_outlier']:>6} | {s['outliers_pequenos']:>4}")

    print("\noutl. = outliers / vídeos com mediana conhecida; mult. = multiplicador típico do nicho")
    print(f"canais = canais diferentes entre os outliers; peq. = outliers de canais com até {CANAL_PEQUENO:,} inscritos")
    print(f"Cota gasta: {radar.cota['buscas']} busca(s) e {radar.cota['unidades']} unidade(s) de leitura")

    with open(arquivo_csv, "w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas_csv[0].keys()), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas_csv)
    print(f"Detalhe de cada vídeo salvo em {arquivo_csv}")


if __name__ == "__main__":
    main()
