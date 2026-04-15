document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');
    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'multiMonthYear', // Visualização Anual
        locale: 'pt-br',
        headerToolbar: false, // Usaremos nossos botões personalizados
        selectable: true,
        themeSystem: 'bootstrap5',
        events: '/api/google-events', // Endpoint para carregar os eventos da conta
        dateClick: function(info) {
            document.getElementById('modal_data').value = info.dateStr;
            var modal = new bootstrap.Modal(document.getElementById('modalAgendamento'));
            modal.show();
        }
    });
    calendar.render();

    // Controles customizados
    document.getElementById('btn-prev').addEventListener('click', () => calendar.prev());
    document.getElementById('btn-next').addEventListener('click', () => calendar.next());
    document.getElementById('btn-today').addEventListener('click', () => calendar.today());
});

function visualizarAgendamento(id, titulo, categoria, data, hora, local, desc) {
    // Preenche os campos de um modal de edição (você pode duplicar o modal de agendamento e mudar o ID)
    $('#edit_titulo').val(titulo);
    $('#edit_categoria').val(categoria);
    $('#edit_data').val(data);
    $('#edit_hora').val(hora);
    $('#edit_localizacao').val(local);
    $('#edit_descricao').val(desc);
    $('#edit_id').val(id);
    $('#modalEdicao').modal('show');
}

/**
 * Captura os dados da linha da tabela e preenche o Modal de Edição
 */
function abrirModalEdicao(id, titulo, cat, data, hora, local, desc, emails) {
    console.log("Editando agendamento ID:", id);
    
    // 1. Preenche os campos do formulário usando IDs definidos no seu HTML
    document.getElementById('edit_titulo').value = titulo;
    document.getElementById('edit_categoria').value = cat;
    document.getElementById('edit_data').value = data;
    document.getElementById('edit_hora').value = hora;
    document.getElementById('edit_localizacao').value = local;
    document.getElementById('edit_descricao').value = desc;
    document.getElementById('edit_participantes').value = emails;

    // 2. Ajusta dinamicamente a URL de destino (Action) do formulário
    document.getElementById('formEdicao').action = '/editar-agendamento/' + id;
    
    // 3. Abre o modal usando a API nativa do Bootstrap 5
    var modalElement = document.getElementById('modalEdicao');
    var myModal = bootstrap.Modal.getOrCreateInstance(modalElement);
    myModal.show();
}