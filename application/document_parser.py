"""
Extração segura de texto de uploads (PDF, DOCX, TXT).
Sem alteração ao score_engine; uso apenas como contexto conversacional.
"""

import io
from typing import Any

# Limite por arquivo (bytes). Alinhado a um uso razoável em SaaS; ajustável via ambiente.
MAX_UPLOAD_BYTES_DEFAULT = 5 * 1024 * 1024  # 5 MiB

# Evita contextos gigantes no LLM mesmo após extração.
MAX_TEXTO_EXTRAIDO_CHARS = 120_000


def extrair_texto_pdf(file_bytes: bytes) -> str:
    import fitz

    if not file_bytes:
        return ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        partes = []
        for page in doc:
            partes.append(page.get_text() or "")
        return "\n".join(partes).strip()
    finally:
        doc.close()


def extrair_texto_docx(file_bytes: bytes) -> str:
    from docx import Document

    if not file_bytes:
        return ""
    buf = io.BytesIO(file_bytes)
    document = Document(buf)
    linhas = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    return "\n".join(linhas).strip()


def extrair_texto_txt(file_bytes: bytes) -> str:
    if not file_bytes:
        return ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace").strip()


def _extensao_segura(nome: str) -> str:
    if not nome or "." not in nome:
        return ""
    return nome.rsplit(".", 1)[-1].lower().strip()


def parse_documento(
    uploaded_file: Any,
    *,
    max_bytes: int = MAX_UPLOAD_BYTES_DEFAULT,
    max_chars: int = MAX_TEXTO_EXTRAIDO_CHARS,
) -> str:
    """
    Extrai texto com base na extensão do nome do arquivo (não confia apenas no MIME).
    """
    nome = getattr(uploaded_file, "name", "") or ""
    ext = _extensao_segura(nome)
    if ext not in {"pdf", "docx", "txt"}:
        raise ValueError("Tipo de arquivo não permitido. Use PDF, DOCX ou TXT.")

    tamanho_decl = getattr(uploaded_file, "size", None)
    if tamanho_decl is not None and int(tamanho_decl) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValueError(f"Arquivo acima do limite de {mb} MiB. Envie um arquivo menor.")

    dados = uploaded_file.getvalue()
    if len(dados) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValueError(f"Arquivo acima do limite de {mb} MiB. Envie um arquivo menor.")

    try:
        if ext == "pdf":
            texto = extrair_texto_pdf(dados)
        elif ext == "docx":
            texto = extrair_texto_docx(dados)
        else:
            texto = extrair_texto_txt(dados)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Não foi possível ler este documento. Verifique se o arquivo está íntegro.") from exc

    if not (texto or "").strip():
        texto = "(Não foi extraído texto legível deste arquivo.)"

    if len(texto) > max_chars:
        texto = texto[:max_chars].rstrip() + "\n\n[... conteúdo truncado por limite de tamanho ...]"

    return texto
