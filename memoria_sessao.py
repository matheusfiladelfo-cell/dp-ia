import uuid
from datetime import datetime


class MemoriaSessao:

    def __init__(self):
        self.sessao_id = str(uuid.uuid4())

        self.historico = []

        self.dados = {
            "tipo_caso": None,
            "tipo_rescisao": None,
            "tempo_empresa_meses": None,
            "gestante": None,
            "cipa": None,
            "dirigente_sindical": None,
            "acidente_trabalho": None,
            "retorno_inss": None
        }

    # =========================
    # HISTÓRICO
    # =========================

    def adicionar(self, role, texto):
        self.historico.append({
            "role": role,
            "texto": texto,
            "timestamp": datetime.now().isoformat()
        })

    def contexto_texto(self, limite=6):
        ultimas = self.historico[-limite:]

        contexto = ""
        for m in ultimas:
            prefixo = "Usuário" if m["role"] == "user" else "Consultor"
            contexto += f"{prefixo}: {m['texto']}\n"

        return contexto

    # =========================
    # MEMÓRIA INTELIGENTE 🔥
    # =========================

    def atualizar_dados(self, novos_dados):

        for chave, valor in novos_dados.items():

            if chave not in self.dados:
                continue

            # 🔥 ignora lixo
            if valor is None:
                continue

            # 🔥 prioridade para informação nova
            if self.dados[chave] is None:
                self.dados[chave] = valor
            else:
                # 🔥 atualiza somente se for mudança relevante
                if self.dados[chave] != valor:
                    self.dados[chave] = valor

    def obter_dados(self):
        return self.dados

    # =========================
    # CONTEXTO COMPLETO
    # =========================

    def gerar_contexto_llm(self):

        return f"""
HISTÓRICO DA CONVERSA:
{self.contexto_texto()}

DADOS CONSOLIDADOS:
{self.dados}
"""