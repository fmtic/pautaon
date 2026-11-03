from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.rss import AvisoTicker
from app.registros import servico_social

# Se estiver usando o blueprint main já existente ou criando um novo bp chamado rss_bp:
# (Ajuste 'main' conforme o nome do seu blueprint nesse arquivo)
rss_bp = Blueprint('rss', __name__, template_folder='../templates')

# --- 1. Rota JSON para o Frontend (Consumido pelo JS na Topbar) ---
@rss_bp.route('/api/ticker/json', methods=['GET'])
def get_ticker_json():
    aviso = AvisoTicker.query.filter_by(ativo=True).order_by(AvisoTicker.id.desc()).first()
    texto_padrao = "Seja bem-vindo ao pautaON - Sistema de Gestão Educacional."
    return jsonify({"texto": aviso.texto if aviso else texto_padrao})


# --- 2. Tela Administrativa para Gerenciar Avisos ---
@rss_bp.route('/ticker/gerenciar', methods=['GET', 'POST'])
@login_required
def gerenciar_ticker():
    if current_user.role not in ['admin', 'gerencia', 'pedagogico', 'secretaria', 'servico_social']:
        flash("Acesso não autorizado.", "danger")
        return redirect(url_for('main.painel'))

    if request.method == 'POST':
        texto = request.form.get('texto', '').strip()
        
        if not texto:
            flash("O texto do aviso não pode ser vazio.", "warning")
            return redirect(url_for('rss.gerenciar_ticker'))

        # Desativa os anteriores para manter apenas o atual ativo
        AvisoTicker.query.update({AvisoTicker.ativo: False})

        novo_aviso = AvisoTicker(texto=texto, ativo=True)
        db.session.add(novo_aviso)
        db.session.commit()

        flash("Aviso do letreiro atualizado com sucesso!", "success")
        return redirect(url_for('rss.gerenciar_ticker'))

    avisos = AvisoTicker.query.order_by(AvisoTicker.id.desc()).limit(10).all()
    # Apontando para o diretório de templates que você escolheu
    return render_template('utils/gerenciar_ticker.html', avisos=avisos)