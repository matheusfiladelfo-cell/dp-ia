from ia_client import client
import json


def analisar_texto_ia(texto):

    prompt = f"""
Você é um analisador jurídico.

REGRAS CRÍTICAS:
- NÃO inventar informações
- Se não estiver explícito no texto → usar null
- NÃO assumir gestante, CIPA ou estabilidade sem evidência
- Seja literal

Retorne JSON válido:

{{
  "tipo_caso": "rescisao | afastamento | duvida_geral",

  "tipo_rescisao": "justa_causa | pedido_demissao | demissao_sem_justa_causa | null",

  "gestante": true/false/null,
  "cipa": true/false/null,
  "dirigente_sindical": true/false/null,
  "acidente_trabalho": true/false/null,
  "retorno_inss": true/false/null,

  "tempo_empresa_meses": número ou null,
  "dias_afastamento": número ou null
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

        dados = json.loads(texto_resposta)

        # 🔥 TRAVA FINAL (ANTI-ALUCINAÇÃO)
        for campo in ["gestante", "cipa", "dirigente_sindical"]:
            if dados.get(campo) not in [True, False, None]:
                dados[campo] = None

        return dados

    except Exception as e:

        return {
            "erro": str(e),
            "tipo_caso": "rescisao"
        }