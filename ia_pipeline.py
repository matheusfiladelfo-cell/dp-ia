from ia_client import client
import json


def analisar_texto_ia(texto):

    prompt = f"""
Você é um analisador trabalhista.

REGRAS CRÍTICAS:
- NÃO inventar informações
- Se não estiver explícito → usar null
- Seja literal e objetivo

Extraia:

- tipo_caso (rescisao, afastamento, duvida_geral)
- tipo_rescisao (justa_causa, pedido_demissao, demissao_sem_justa_causa)
- tempo_empresa_meses (número)
- dias_afastamento (número)

🔥 NOVO:
- salario (valor numérico, ex: 1800)
- horas_extras_semanais (número, ex: 2)

Estabilidades:
- gestante
- cipa
- dirigente_sindical
- acidente_trabalho
- retorno_inss

Retorne JSON válido:

{{
  "tipo_caso": "",
  "tipo_rescisao": null,
  "tempo_empresa_meses": null,
  "dias_afastamento": null,
  "salario": null,
  "horas_extras_semanais": null,
  "gestante": null,
  "cipa": null,
  "dirigente_sindical": null,
  "acidente_trabalho": null,
  "retorno_inss": null
}}

Texto:
\"\"\"{texto}\"\"\"
"""

    try:

        resposta = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            timeout=10
        )

        texto_resposta = resposta.output_text.strip()

        if "```" in texto_resposta:
            texto_resposta = texto_resposta.split("```")[1]

        dados = json.loads(texto_resposta)

        # 🔥 TRAVA ANTI-ALUCINAÇÃO
        for campo in ["gestante", "cipa", "dirigente_sindical"]:
            if dados.get(campo) not in [True, False, None]:
                dados[campo] = None

        return dados

    except Exception as e:

        return {
            "erro": str(e)
        }