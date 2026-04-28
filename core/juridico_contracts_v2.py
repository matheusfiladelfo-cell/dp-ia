from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RiscoNivel(str, Enum):
    BAIXO = "BAIXO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    INCONCLUSIVO = "INCONCLUSIVO"


class TipoRisco(str, Enum):
    ASSEDIO_MORAL = "assedio_moral"
    ACIDENTE_TRABALHO = "acidente_trabalho"
    CONFLITO_INTERPESSOAL = "conflito_interpessoal"
    RESCISAO = "rescisao"
    AFASTAMENTO = "afastamento"
    HORA_EXTRA = "hora_extra"
    GERAL = "geral"
    INCONCLUSIVO = "inconclusivo"


class StatusEvidencia(str, Enum):
    FORTE = "forte"
    MODERADA = "moderada"
    FRACA = "fraca"
    AUSENTE = "ausente"


@dataclass
class EvidenciaJuridica:
    descricao: str
    fonte: str
    status: StatusEvidencia = StatusEvidencia.MODERADA
    peso: float = 1.0


@dataclass
class ClassificacaoJuridicaV2:
    tipo_risco: TipoRisco = TipoRisco.GERAL
    gravidade: RiscoNivel = RiscoNivel.BAIXO
    confianca_classificacao: float = 0.5
    evidencias_detectadas: List[EvidenciaJuridica] = field(default_factory=list)
    lacunas_informacao: List[str] = field(default_factory=list)
    flags_criticas: List[str] = field(default_factory=list)


@dataclass
class ScoreBreakdownItem:
    fator: str
    peso: float
    contribuicao: float
    observacao: str = ""


@dataclass
class ScoreJuridicoV2:
    risco_juridico: RiscoNivel = RiscoNivel.INCONCLUSIVO
    score_total: int = 0
    nivel_confianca_score: str = "medio"
    probabilidade_condenacao: int = 0
    score_breakdown: List[ScoreBreakdownItem] = field(default_factory=list)


@dataclass
class ParecerJuridicoV2:
    diagnostico_factual: str = ""
    fundamentacao_juridica: str = ""
    teses_risco: List[str] = field(default_factory=list)
    teses_defesa: List[str] = field(default_factory=list)
    recomendacoes_24h: List[str] = field(default_factory=list)
    recomendacoes_7d: List[str] = field(default_factory=list)
    recomendacoes_30d: List[str] = field(default_factory=list)
    nivel_confianca: str = "medio"
    lacunas_informacao: List[str] = field(default_factory=list)


@dataclass
class NucleoJuridicoOutputV2:
    classificacao: ClassificacaoJuridicaV2
    score: ScoreJuridicoV2
    parecer: Optional[ParecerJuridicoV2] = None
    metadados: Dict[str, str] = field(default_factory=dict)
