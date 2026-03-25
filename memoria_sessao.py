import uuid
from datetime import datetime


class MemoriaSessao:

    def __init__(self):
        self.sessao_id = str(uuid.uuid4())

        self.historico = []

        # 🔥 AGORA COMPLETO
        self.dados = {
            "tipo_caso": None,
            "tipo_rescisao": None,
            "tempo_empresa_meses": None,
            "dias_afastamento": None,

            # 🔥 NOVOS CAMPOS (CRÍTICO)
            "salario": None,
            "horas_extras_semanais": None,

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
    # 🔥 MEMÓRIA CORRIGIDA
    # =========================

    def atualizar_dados(self, novos_dados):

        for chave, valor in novos_dados.items():

            # 🔥 agora aceita novos campos
            if valor is None:
                continue

            # 🔥 cria campo se não existir
            if chave not in self.dados:
                self.dados[chave] = valor
                continue

            # 🔥 sempre atualiza (remove bug antigo)
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