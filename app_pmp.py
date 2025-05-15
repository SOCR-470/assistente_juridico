import os
import re
import streamlit as st
from dotenv import load_dotenv
import requests
import openai

# Configurações iniciais
print("✅ Iniciando app_pmp.py")
load_dotenv()

# Configuração da API OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constantes e configurações
ESCRITORIO = {
    "nome_display": "Pinheiro Machado & Pinto",
    "logo_url": "https://raw.githubusercontent.com/SOCR-470/assistente_juridico/main/logo_pmp.png",
    "titulo_sub": "Pinheiro Machado & Pinto"
}

LINK_GOOGLE_CALENDAR = os.getenv("LINK_CALENDAR") or "https://calendar.google.com/calendar/u/0/selfsched?sstoken=XXXXXXXXXX"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_CONTRATUAL")

# Configuração da interface
st.set_page_config(
    page_title=ESCRITORIO["nome_display"],
    page_icon=ESCRITORIO["logo_url"]
)

# Componentes de UI
def exibir_cabecalho():
    st.markdown(
        f"""
        <div style='text-align: center'>
            <img src='{ESCRITORIO["logo_url"]}' width='260'/>
            <h4 style='margin-top: 0.5em; color: gray;'>{ESCRITORIO["titulo_sub"]}</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

# Estados da conversa
def inicializar_estados():
    if "etapa" not in st.session_state:
        st.session_state.etapa = "coleta_dados"
        st.session_state.dados_cliente = {}
        st.session_state.agendamento_solicitado = False
        st.session_state.historico_chat = [{
            "role": "system",
            "content": f"""
            Você é Luana, assistente virtual do escritório {ESCRITORIO["nome_display"]}. Siga ESTES PASSOS À RISCA:

            1. SAUDAÇÃO INICIAL:
            - Sempre comece com: "Olá, seja bem-vindo ao {ESCRITORIO["nome_display"]}. Meu nome é Luana e irei cuidar de seu atendimento. Poderia, primeiramente, me informar seu *nome completo* e *telefone com DDD*, por gentileza?"
            - Não faça outras perguntas nesta etapa.

            2. VALIDAÇÃO DE DADOS:
            - Se faltar nome OU telefone, diga exatamente: "Para podermos prosseguir, preciso do seu *nome completo* e *telefone com DDD*."
            - Se tiver ambos, confirme: "Obrigada {{nome}}! Como posso ajudar hoje?"

            3. COLETA DO ASSUNTO:
            - Peça breve descrição do assunto usando: "Poderia me informar resumidamente sobre qual assunto deseja tratar?"
            - Faça no máximo 2 perguntas claras para entender o contexto

            4. FINALIZAÇÃO:
            - Ofereça agendamento: "Deseja agendar uma reunião com nossos especialistas?"
            - Se positivo, ENVIE APENAS O LINK: {LINK_GOOGLE_CALENDAR}
            - Se negativo, encerre com: "Estamos à disposição para qualquer necessidade futura!"

            REGRAS:
            - NUNCA liste áreas de atuação
            - Mantenha respostas curtas (máx 2 linhas)
            - Use emojis moderadamente
            - Valide dados antes de prosseguir
            - Formate números telefônicos automaticamente
            """
        }]

# Funções auxiliares
def validar_contato(texto):
    nome = re.search(r"[A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]{2,})+", texto)
    telefone = re.search(r"(\d{2})\D*(\d{4,5}\D*\d{4})", texto)
    return bool(nome and telefone)

def formatar_telefone(texto):
    match = re.search(r"(\d{2})\D*(\d{4,5})\D*(\d{4})", texto)
    if match:
        return f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
    return None

def enviar_telegram(historico):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    mensagem = "📋 *Novo Atendimento*\n\n"
    for msg in historico:
        if msg["role"] == "user":
            mensagem += f"👤: {msg['content']}\n"
        elif msg["role"] == "assistant":
            mensagem += f"🤖: {msg['content']}\n"
    
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown"
        }
    )

# Fluxo principal
exibir_cabecalho()
inicializar_estados()

# Processamento de entrada
entrada_usuario = st.chat_input("Digite aqui sua mensagem...")

if entrada_usuario:
    # Atualizar histórico
    st.session_state.historico_chat.append({"role": "user", "content": entrada_usuario})
    
    # Lógica de validação
    if st.session_state.etapa == "coleta_dados":
        if validar_contato(entrada_usuario):
            st.session_state.etapa = "assunto"
            st.session_state.dados_cliente = {
                "nome": ' '.join(re.findall(r"[A-Za-zÀ-ÿ]+", entrada_usuario)[:2]),
                "telefone": formatar_telefone(entrada_usuario)
            }
    
    # Gerar resposta
    with st.spinner("Luana está digitando..."):
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.historico_chat,
            temperature=0.2
        )
        conteudo = resposta.choices[0].message.content
        
        # Pós-processamento
        if "agendar" in conteudo.lower() and not st.session_state.agendamento_solicitado:
            conteudo += f"\n\n📅 [Agendar reunião aqui]({LINK_GOOGLE_CALENDAR})"
            st.session_state.agendamento_solicitado = True
        
        st.session_state.historico_chat.append({"role": "assistant", "content": conteudo})
    
    # Envio para Telegram
    if st.session_state.etapa == "assunto":
        enviar_telegram(st.session_state.historico_chat)

# Exibir histórico
for msg in st.session_state.historico_chat[1:]:  # Ignorar system prompt
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.write(msg["content"])
        if msg["role"] == "assistant" and LINK_GOOGLE_CALENDAR in msg["content"]:
            st.markdown(f"[📅 Agendar diretamente]({LINK_GOOGLE_CALENDAR})")