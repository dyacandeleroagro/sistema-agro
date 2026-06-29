import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="D&A Candelero Agro", layout="wide")

st.title("🚜 D&A Candelero Agro - Conexión Directa")

# Aquí simplemente pondremos una forma de ver si carga, 
# para no tener errores de código complejos al principio.
st.write("Sistema listo para conectar a Google Sheets.")

# Esta es la base para tu app. Si esto abre bien, 
# luego solo tenemos que configurar las credenciales de Google.