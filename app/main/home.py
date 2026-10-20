from flask import render_template

from . import bp


@bp.route("/")
def home():
    """Portal de Entrada do Sistema."""
    return render_template("login.html")

import os
from pathlib import Path

@bp.route("/politica_privacidade")
def politica_privacidade():
    """Exibe a política de privacidade."""
    markdown_path = Path(__file__).parent.parent.parent / "static" / "uploads" / "politica_de_privacidade_pautaon.md"
    
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "Arquivo não encontrado."
    
    # Conversão simples de markdown para HTML
    html_content = _simple_markdown_to_html(content)
    
    return render_template("termos/politica_privacidade.html", content=html_content)


@bp.route("/termos_servico")
def termos_servico():
    """Exibe os termos de serviço."""
    markdown_path = Path(__file__).parent.parent.parent / "static" / "uploads" / "termos_de_servico_pautaon.md"
    
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "Arquivo não encontrado."
    
    # Conversão simples de markdown para HTML
    html_content = _simple_markdown_to_html(content)
    
    return render_template("termos/termos_servico.html", content=html_content)


def _simple_markdown_to_html(text: str) -> str:
    """Conversão simples de Markdown para HTML sem dependências externas."""
    import re
    
    # Substituições básicas
    html = text
    
    # Headers (# ## ###)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold (**texto**)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Italic (*texto*)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Links [texto](url)
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', html)
    
    # Listas (linhas que começam com - ou *)
    lines = html.split('\n')
    in_list = False
    result = []
    
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            content = line.strip()[2:]
            result.append(f'<li>{content}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            if line.strip():
                result.append(f'<p>{line}</p>')
    
    if in_list:
        result.append('</ul>')
    
    return '\n'.join(result)
