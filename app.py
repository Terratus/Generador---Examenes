import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import google.generativeai as genai
import PyPDF2
import docx
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ExamenMatic AI", page_icon="🧠", layout="centered")

# --- 2. AUTENTICACIÓN ---
# Cargar configuración
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("Error: No se encontró el archivo config.yaml")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Widget de Login
name, authentication_status, username = authenticator.login('main')

if authentication_status is False:
    st.error('Usuario o contraseña incorrectos')
elif authentication_status is None:
    st.warning('Por favor, ingresa tus credenciales para acceder.')

elif authentication_status is True:
    # =======================================================
    #        AQUÍ COMIENZA LA APLICACIÓN (ÁREA SEGURA)
    # =======================================================

    # Inicializar estado para resetear
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

    def reset_app():
        st.session_state.uploader_key += 1

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.success(f"Bienvenido, **{name}**")
        authenticator.logout('Cerrar Sesión', 'sidebar')
        st.divider()
        
        # Logo
        try: st.image("logo.png", width=200)
        except: st.header("🤖 Terratus")
        
        st.subheader("Configuración")
        api_key = st.text_input("🔑 API Key Google:", type="password")
        
        difficulty = st.selectbox("Nivel:", ["Fácil", "Intermedio", "Difícil"])
        num_questions = st.slider("Preguntas:", 3, 20, 5)
        
        st.markdown("---")
        if st.button("🔄 Reiniciar App", on_click=reset_app):
            st.write("Limpiando...")

    # --- FUNCIONES DE LECTURA ---
    def extract_from_pdf(file):
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages: text += page.extract_text() or ""
        return text

    def extract_from_docx(file):
        doc = docx.Document(file)
        text = ""
        for para in doc.paragraphs: text += para.text + "\n"
        return text
    
    def extract_from_txt(file): return file.getvalue().decode("utf-8")

    # --- FUNCIONES DE EXPORTACIÓN ---
    def create_word_file(text):
        doc = docx.Document()
        for p in text.split('\n'): 
            if p.strip(): doc.add_paragraph(p)
        b = BytesIO(); doc.save(b); b.seek(0)
        return b

    def create_pdf_file(text):
        b = BytesIO(); c = canvas.Canvas(b, pagesize=letter); w, h = letter
        c.setFont("Helvetica", 12); y = h - 50; margin = 50
        for line in text.split('\n'):
            wrapped = simpleSplit(line, "Helvetica", 12, w - 2*margin)
            for wl in wrapped:
                if y < 50: c.showPage(); c.setFont("Helvetica", 12); y = h-50
                c.drawString(margin, y, wl); y -= 15
            y-=5
        c.save(); b.seek(0)
        return b

    # --- FUNCIÓN IA ---
    def generate_quiz(text, api_key, num, level):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"""
            Actúa como profesor experto.
            1. Crea {num} preguntas de nivel {level} sobre el texto. NO marques la respuesta correcta aquí.
            2. Escribe una línea exacta: "---SOLUCIONARIO---"
            3. Escribe las respuestas correctas con justificación.
            Texto: {text[:10000]}
            """
            return model.generate_content(prompt).text
        except Exception as e: return f"Error: {e}"

    # --- INTERFAZ PRINCIPAL ---
    st.title("🎓 Generador de Exámenes Pro")
    st.markdown("Genera evaluaciones en segundos a partir de tus documentos.")

    uploaded_file = st.file_uploader(
        "Sube tu archivo (PDF, DOCX, TXT)", 
        type=["pdf", "docx", "txt"],
        key=str(st.session_state.uploader_key)
    )

    if uploaded_file and api_key:
        if st.button("🚀 Generar Examen"):
            with st.spinner("Leyendo documento y creando preguntas..."):
                ftype = uploaded_file.name.split('.')[-1].lower()
                raw = ""
                try:
                    if ftype == 'pdf': raw = extract_from_pdf(uploaded_file)
                    elif ftype == 'docx': raw = extract_from_docx(uploaded_file)
                    elif ftype == 'txt': raw = extract_from_txt(uploaded_file)
                except: st.error("No se pudo leer el archivo."); st.stop()

                if len(raw) > 50:
                    res = generate_quiz(raw, api_key, num_questions, difficulty)
                    
                    if "---SOLUCIONARIO---" in res:
                        parts = res.split("---SOLUCIONARIO---")
                        exam, sol = parts[0], parts[1]
                    else:
                        exam, sol = res, "Error separando respuestas."

                    st.success("¡Examen generado!")
                    
                    tab1, tab2 = st.tabs(["📄 Cuestionario", "🔐 Solucionario"])
                    
                    with tab1:
                        st.markdown(exam)
                        c1, c2 = st.columns(2)
                        c1.download_button("Descargar Word", create_word_file(exam), "examen.docx")
                        c2.download_button("Descargar PDF", create_pdf_file(exam), "examen.pdf")
                    
                    with tab2:
                        st.markdown(sol)
                        c3, c4 = st.columns(2)
                        c3.download_button("Descargar Word", create_word_file(sol), "solucionario.docx", key='w2')
                        c4.download_button("Descargar PDF", create_pdf_file(sol), "solucionario.pdf", key='p2')
                else:
                    st.warning("El documento tiene muy poco texto.")

    elif uploaded_file and not api_key:
        st.warning("AIzaSyB01nF2UTVfNJGRK90khuE51mG2BQcUCsI")

    # --- PIE DE PÁGINA ---
    st.markdown("Charles J. Martín M. Arredondo")
    st.markdown("<center><small>Desarrollado con ❤️ y Gemini AI</small></center>", unsafe_allow_html=True)