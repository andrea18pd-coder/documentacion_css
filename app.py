import streamlit as st

from lib.auth import login_form, is_logged_in, is_admin, restore_session
from lib.ui import inject_css, page_header, top_bar

st.set_page_config(page_title="Q10 · Documentación CSS", page_icon="🤓", layout="wide")

inject_css()
restore_session()

if not is_logged_in():
    top_bar(None)
    page_header("Documentación CSS", "Consulta y gestión de la documentación del área")
    st.markdown("### Iniciar sesión")
    login_form()
    # Sin rerun explícito en login_form(): si el login tuvo éxito en esta misma corrida,
    # is_logged_in() ya es True aquí y seguimos de largo hacia la navegación normal, sin
    # cortar con st.stop(). Solo se corta si el login todavía no ha ocurrido/fallado.
    if not is_logged_in():
        st.stop()

pages = [
    st.Page("pages/0_Anuncios.py", title="Anuncios", icon="📢"),
    st.Page("pages/1_Funcionalidades.py", title="Funcionalidades", default=True),
    st.Page("pages/2_Desarrollos_Personalizados.py", title="Desarrollos personalizados"),
    st.Page("pages/3_Dimensiones.py", title="Dimensiones"),
    st.Page("pages/4_APIs.py", title="APIs"),
    st.Page("pages/6_Queries.py", title="Queries"),
    st.Page("pages/7_Biblioteca_Desarrollos.py", title="Biblioteca de desarrollos"),
    st.Page("pages/8_Sentencias_Nivel_II.py", title="Sentencias - Nivel II"),
]
if is_admin():
    pages.append(st.Page("pages/5_Administracion.py", title="Administración", icon="⚙️"))

navigation = st.navigation(pages)
navigation.run()
