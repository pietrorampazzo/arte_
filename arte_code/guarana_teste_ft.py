import os
import json
import re
from typing import List

import pandas as pd

from arte_code.model_manager import GoogleModelManager
from arte_code.rate_limiter import create_rate_limiter
from arte_code.prompt_templates import build_prompt_categorizacao, build_prompt_selecao


def parse_llm_response(response_text: str):
    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def categorizar_item(model_manager: GoogleModelManager, rate_limiter, descricao: str) -> str:
    prompt = build_prompt_categorizacao(descricao)
    if not rate_limiter.wait_if_needed([descricao, "categorizacao", "json"]):
        return "OUTROS"
    response = model_manager.generate(prompt)
    parsed = parse_llm_response(response.text)
    if parsed and len(parsed) > 0:
        return parsed[0].get("CATEGORIA_PRINCIPAL", "OUTROS")
    return "OUTROS"


def selecionar_melhor(model_manager: GoogleModelManager, rate_limiter, item_data: dict, base_filtrada_json: str) -> List[str]:
    prompt = build_prompt_selecao(item_data, base_filtrada_json)
    textos: List[str] = [
        item_data.get("DESCRICAO", ""),
        str(item_data.get("VALOR_UNIT", "")),
        base_filtrada_json[:4000],
    ]
    if not rate_limiter.wait_if_needed(textos):
        return ["N/A", "N/A", "N/A", "N/A", "N/A", "0%"]
    response = model_manager.generate(prompt)
    tabela_texto = response.text.strip()
    linhas = [linha for linha in tabela_texto.split("\n") if "|" in linha and not linha.strip().startswith("|--")]
    if len(linhas) > 0:
        linha_dados = linhas[-1]
        colunas = [col.strip() for col in linha_dados.strip("|").split("|")]
        if len(colunas) >= 6:
            rate_limiter.record_request(textos, success=True)
            return colunas
    rate_limiter.record_request(textos, success=False)
    return ["N/A", "N/A", "N/A", "N/A", "N/A", "0%"]


def main():
    # Configuração
    model_manager = GoogleModelManager()  # Requer GOOGLE_API_KEY no ambiente
    rate_limiter = create_rate_limiter()

    CAMINHO_EDITAL = r"mster_estudo.xlsx"
    CAMINHO_BASE = r"RESULTADO/produtos_categorizados.xlsx"
    output_dir = r"RESULTADO"
    CAMINHO_SAIDA = os.path.join(output_dir, "arte_heavy_categorizado_V3_claude.xlsx")

    # Carregamento
    try:
        df_edital = pd.read_excel(CAMINHO_EDITAL)
        df_base = pd.read_excel(CAMINHO_BASE)
        print(f"✅ Edital: {len(df_edital)} itens | Base: {len(df_base)} produtos")
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        return

    df_base.columns = df_base.columns.str.strip()

    resultados: List[dict] = []
    total_itens = len(df_edital)

    for idx, row in df_edital.iterrows():
        item_data = row.to_dict()
        print(f"Processando item {idx + 1}/{total_itens}: {str(item_data.get('DESCRICAO', ''))[:50]}...")

        # Categorizar
        categoria = categorizar_item(model_manager, rate_limiter, item_data.get("DESCRICAO", ""))

        # Filtrar base
        df_filtrado = df_base[df_base["categoria_principal"] == categoria]

        # Restrições de preço
        try:
            valor_unit = float(item_data.get("VALOR_UNIT", 0))
        except Exception:
            valor_unit = 0.0
        df_filtrado = df_filtrado[df_filtrado["VALOR_MARGEM"] <= valor_unit]

        if df_filtrado.empty:
            print(f"⚠️ Sem produtos na categoria {categoria} com a margem válida")
            colunas = ["N/A", "N/A", "N/A", "N/A", "N/A", "0%"]
        else:
            base_json = (
                df_filtrado[
                    [
                        "categoria_principal",
                        "subcategoria",
                        "MARCA",
                        "MODELO",
                        "VALOR_MARGEM",
                        "DESCRICAO",
                    ]
                ]
                .head(200)
                .to_json(orient="records", force_ascii=False, indent=2)
            )

            # Selecionar melhor via LLM
            colunas = selecionar_melhor(model_manager, rate_limiter, item_data, base_json)

        resultados.append(
            {
                "ARQUIVO": item_data.get("ARQUIVO", ""),
                "Nº": item_data.get("Nº", ""),
                "DESCRICAO": item_data.get("DESCRICAO", ""),
                "UNID_FORN": item_data.get("UNID_FORN", ""),
                "QTDE": item_data.get("QTDE", 0),
                "VALOR_UNIT": item_data.get("VALOR_UNIT", 0),
                "VALOR_TOTAL": item_data.get("VALOR_TOTAL", 0),
                "LOCAL_ENTREGA": item_data.get("LOCAL_ENTREGA", ""),
                "Marca Sugerida": colunas[0],
                "Modelo Sugerido": colunas[1],
                "Preço Fornecedor": colunas[2],
                "Preço com Margem 53%": colunas[3],
                "Descrição Fornecedor": colunas[4],
                "% Compatibilidade": colunas[5],
            }
        )

    if resultados:
        colunas_exportacao = [
            "ARQUIVO",
            "DESCRICAO",
            "VALOR_UNIT",
            "VALOR_TOTAL",
            "LOCAL_ENTREGA",
            "Nº",
            "UNID_FORN",
            "QTDE",
            "Marca Sugerida",
            "Modelo Sugerido",
            "Preço com Margem 53%",
            "Preço Fornecedor",
            "Descrição Fornecedor",
            "% Compatibilidade",
        ]
        df_resultados = pd.DataFrame(resultados)[colunas_exportacao]
        os.makedirs(output_dir, exist_ok=True)
        df_resultados.to_excel(CAMINHO_SAIDA, index=False)
        print(f"✅ Exportado: {CAMINHO_SAIDA}")
    else:
        print("⚠️ Sem resultados")


if __name__ == "__main__":
    # Garante que a variável de ambiente da API esteja presente
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️ Defina a variável de ambiente GOOGLE_API_KEY antes de executar.")
    main()

