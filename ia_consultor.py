from ia_client import client
import json


def gerar_parecer_juridico(contexto, dados, resultado):

    prompt = f"""
Você é um advogado trabalhista especialista.

Analise o caso com base em:

- CLT
- Constituição Federal
- Jurisprudência do TST

---

DADOS:
{dados}

---

OBJETIVO:

Retornar uma análise jurídica REAL.

---

REGRAS:

- NÃO inventar fatos
- Se faltar informação → considerar risco maior
- Justa causa exige prova robusta
- Sempre considerar chance de reversão judicial

---

RETORNE JSON VÁLIDO:

{{
  "diagnostico": "...",
  "risco": "BAIXO | MÉDIO | ALTO",
  "fundamentacao": "...",
  "recomendacao": "..."
}}
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            timeout=15
        )

        texto = resposta.output_text.strip()

        return json.loads(texto)

    except Exception as e:
        return {
            "diagnostico": "Erro na análise",
            "risco": "MÉDIO",
            "fundamentacao": str(e),
            "recomendacao": "Revisar manualmente"
        }