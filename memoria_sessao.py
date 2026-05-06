import uuid
from datetime import datetime

from application.document_fatos_llm import formatar_fatos_para_contexto_llm


class MemoriaSessao:

    def __init__(self):
        self.sessao_id = str(uuid.uuid4())

        self.historico = []
        self.sinais_identificados = []

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

    def adicionar(self, role, texto, arquivo=None, fatos_extraidos=None, fatos_ia_originais=None):
        item = {
            "role": role,
            "texto": texto,
            "timestamp": datetime.now().isoformat(),
        }
        if arquivo is not None:
            item["arquivo"] = arquivo
        if role == "document":
            item["doc_msg_uid"] = str(uuid.uuid4())
            if fatos_extraidos is not None:
                item["fatos_extraidos"] = fatos_extraidos
            if fatos_ia_originais is not None:
                item["fatos_ia_originais"] = fatos_ia_originais
        self.historico.append(item)
        if role == "user":
            self._identificar_sinais(texto)

    def atualizar_mensagem_documento(self, doc_msg_uid: str, campos: dict) -> bool:
        for m in self.historico:
            if m.get("doc_msg_uid") == doc_msg_uid:
                m.update(campos)
                return True
        return False

    def contexto_texto(self, limite=6):
        if limite is None:
            ultimas = self.historico
        else:
            ultimas = self.historico[-limite:]

        contexto = ""
        for m in ultimas:
            role = m.get("role")
            if role == "user":
                prefixo = "Usuário"
            elif role == "document":
                nome_doc = str(m.get("arquivo") or "documento")
                prefixo = f"Documento anexado ({nome_doc})"
            else:
                prefixo = "Consultor"
            corpo = m["texto"]
            if role == "document":
                fatos_doc = m.get("fatos_extraidos")
                if fatos_doc:
                    corpo += "\n\n" + formatar_fatos_para_contexto_llm(fatos_doc)
            contexto += f"{prefixo}: {corpo}\n"

        return contexto

    def historico_completo_texto(self):
        return self.contexto_texto(limite=len(self.historico))

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

    def obter_sinais_identificados(self):
        return list(self.sinais_identificados)

    def total_interacoes_usuario(self):
        return sum(1 for m in self.historico if m.get("role") == "user")

    def ha_pergunta_pendente(self):
        if not self.historico:
            return False
        ultima = self.historico[-1]
        texto = str(ultima.get("texto") or "")
        return ultima.get("role") == "assistant" and "?" in texto

    def _identificar_sinais(self, texto):
        texto_lower = str(texto or "").lower()
        sinais_mapa = {
            "pj": [" pj ", "pejotizacao", "pejotização", "prestador", "pessoa juridica", "pessoa jurídica"],
            "fgts": ["fgts", "fundo de garantia"],
            "conflito": ["conflito", "discussao", "discussão", "briga", "ameaça", "ameaca"],
            "assedio": ["assedio", "assédio", "humilh", "constrang"],
            "hora_extra": ["hora extra", "horas extras", "jornada", "ponto"],
            "rescisao": ["rescis", "demiss", "dispensa", "justa causa"],
        }
        base = f" {texto_lower} "
        for sinal, termos in sinais_mapa.items():
            if any(t in base for t in termos) and sinal not in self.sinais_identificados:
                self.sinais_identificados.append(sinal)

    # =========================
    # CONTEXTO COMPLETO
    # =========================

    def gerar_contexto_llm(self):

        return f"""
HISTÓRICO DA CONVERSA:
{self.contexto_texto(limite=None)}

DADOS CONSOLIDADOS:
{self.dados}
"""