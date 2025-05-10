from google_agenda import criar_evento_google_calendar

casos_de_teste = [
    ("Rodrigo Moris", "10/05/2025 às 10h", "Consulta sobre planejamento tributário"),
    ("João da Silva", "11/05/2025 às 20h", "Agendamento fora do horário"),
    ("Maria Souza", "11/05/2025 às 10h", "Verificar duplicidade no mesmo horário"),
    ("Carlos Lima", "12/05 às 15h", "Agendamento com data sem ano informado"),
    ("Ana Teste", "sábado às 11h", "Agendamento em final de semana")
]

for nome, horario, detalhes in casos_de_teste:
    print("\n--- TESTE ---")
    print(f"Cliente: {nome}\nHorário informado: {horario}\nDetalhes: {detalhes}")
    try:
        data, link = criar_evento_google_calendar(nome, horario, detalhes)
        print("Resultado:", data)
        print("Link:", link)
    except Exception as e:
        print("❌ Erro durante o agendamento:", str(e))
    print("-----------------------------")
