import streamlit as st

from lib.auth import login_form, is_logged_in, is_admin
from lib.ui import inject_css, page_header, top_bar

st.set_page_config(page_title="Q10 · Documentación CSS", page_icon="📘", layout="wide")

inject_css()

if not is_logged_in():
    top_bar(None)
    page_header("Documentación CSS", "Consulta y gestión de la documentación del área")
    st.markdown("### Iniciar sesión")
    login_form()
    st.stop()

pages = [
    st.Page("pages/0_Anuncios.py", title="Anuncios", icon="📢"),
    st.Page("pages/1_Funcionalidades.py", title="Funcionalidades", icon="📋"),
    st.Page("pages/2_Desarrollos_Personalizados.py", title="Desarrollos personalizados", icon="🛠️"),
    st.Page("pages/3_Dimensiones.py", title="Dimensiones", icon="📐"),
    st.Page("pages/4_APIs.py", title="APIs", icon="🔌"),
    st.Page("pages/6_Queries.py", title="Queries", icon="🗄️"),
    st.Page("pages/7_Biblioteca_Desarrollos.py", title="Biblioteca de desarrollos", icon="📚"),
]
if is_admin():
    pages.append(st.Page("pages/5_Administracion.py", title="Administración", icon="⚙️"))

navigation = st.navigation(pages)
navigation.run()
