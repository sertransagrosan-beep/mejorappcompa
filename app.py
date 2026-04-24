import requests
import streamlit as st
import time
from datetime import datetime
import pandas as pd
import json

# Configuración
URL_API = "https://consultasimit.fcm.org.co/simit/microservices/estado-cuenta-simit/estadocuenta/consulta"
TIEMPO_ESPERA = 30  # segundos entre consultas

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.fcm.org.co",
    "Referer": "https://www.fcm.org.co/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def consultar_comparendo(cedula, placa, session_cookies=None):
    """Consulta un comparendo - sin necesidad de captcha"""
    
    if session_cookies is None:
        session_cookies = {}
    
    session = requests.Session()
    session.cookies.update(session_cookies)
    
    payload = {
        "filtro": cedula,
        "reCaptchaDTO": {
            "response": f"{{\"time\":{int(time.time())},\"nonce\":\"\"}}"
        }
    }
    
    try:
        response = session.post(URL_API, json=payload, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        elif response.status_code == 429:
            return {"success": False, "error": "Demasiadas consultas. Espera 30 segundos."}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "detail": response.text}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def consultar_multiples(conductores, progreso_callback=None):
    """Consulta múltiples conductores respetando el tiempo de espera"""
    resultados = []
    
    for idx, conductor in enumerate(conductores):
        if progreso_callback:
            progreso_callback(idx, len(conductores), conductor)
        
        resultado = consultar_comparendo(conductor['cedula'], conductor['placa'])
        resultados.append({
            "cedula": conductor['cedula'],
            "placa": conductor['placa'],
            "timestamp": datetime.now().isoformat(),
            "resultado": resultado
        })
        
        if idx < len(conductores) - 1:
            time.sleep(TIEMPO_ESPERA)
    
    return resultados

# ============ APLICACIÓN STREAMLIT ============
st.set_page_config(page_title="Consultor SIMIT", page_icon="🚗")
st.title("🚗 Consultor de Comparendos SIMIT")
st.markdown("Consulta el estado de cuenta de vehículos en Colombia")

with st.sidebar:
    st.header("ℹ️ Información")
    st.info(f"""
    **Límites del sistema:**
    - ⏱️ {TIEMPO_ESPERA} segundos entre consultas
    - 📋 Máximo 25 conductores por lote
    - ⏰ Una consulta masiva toma ~{TIEMPO_ESPERA * 25 / 60:.0f} minutos
    """)

# Consulta individual
with st.expander("🔍 Consulta individual", expanded=True):
    with st.form("consulta_unica"):
        col1, col2 = st.columns(2)
        with col1:
            cedula = st.text_input("Número de cédula", placeholder="Ej: 74370314")
        with col2:
            placa = st.text_input("Placa del vehículo", placeholder="Ej: ABC123")
        
        submitted = st.form_submit_button("Consultar", type="primary")
        
        if submitted:
            if not cedula or not placa:
                st.error("❌ Ingresa cédula y placa")
            else:
                with st.spinner("Consultando SIMIT..."):
                    resultado = consultar_comparendo(cedula, placa)
                
                if resultado.get("success"):
                    st.success("✅ Consulta exitosa")
                    st.json(resultado["data"])
                else:
                    st.error(f"❌ {resultado.get('error')}")

# Consulta masiva
with st.expander("📊 Consulta masiva (hasta 25 conductores)"):
    st.markdown("**Formato:** una línea por conductor, separado por comas: `cédula,placa`")
    
    ejemplo = """74370314,ABC123
98765432,XYZ789
55555555,PQR456"""
    
    conductores_input = st.text_area("Lista de conductores:", ejemplo, height=150)
    
    iniciar = st.button("🚀 Iniciar consulta masiva", type="primary", use_container_width=True)
    
    if iniciar:
        conductores = []
        lineas = [l.strip() for l in conductores_input.strip().split('\n') if l.strip()]
        
        for linea in lineas:
            if ',' in linea:
                partes = linea.split(',')
                if len(partes) >= 2:
                    conductores.append({
                        "cedula": partes[0].strip(),
                        "placa": partes[1].strip()
                    })
        
        if len(conductores) == 0:
            st.error("❌ No se encontraron conductores válidos")
        elif len(conductores) > 25:
            st.error(f"❌ Máximo 25 conductores. Tienes {len(conductores)}.")
        else:
            if st.button("✅ Sí, continuar"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def actualizar_progreso(idx, total, conductor):
                    porcentaje = (idx + 1) / total
                    progress_bar.progress(porcentaje)
                    status_text.markdown(f"""
                    **Consultando:** {idx+1}/{total}
                    - 📝 Cédula: `{conductor['cedula']}`
                    - 🚗 Placa: `{conductor['placa']}`
                    """)
                
                resultados = consultar_multiples(conductores, actualizar_progreso)
                
                status_text.markdown("✅ **¡Consultas completadas!**")
                st.balloons()
                
                resumen_data = []
                for r in resultados:
                    resumen_data.append({
                        "Cédula": r["cedula"],
                        "Placa": r["placa"],
                        "Estado": "✅ Éxito" if r["resultado"].get("success") else "❌ Error",
                    })
                
                df_resumen = pd.DataFrame(resumen_data)
                st.dataframe(df_resumen, use_container_width=True)
                
                export_data = []
                for r in resultados:
                    export_data.append({
                        "cedula": r["cedula"],
                        "placa": r["placa"],
                        "fecha_consulta": r["timestamp"],
                        "exito": r["resultado"].get("success"),
                        "datos": json.dumps(r["resultado"].get("data")) if r["resultado"].get("success") else None,
                        "error": r["resultado"].get("error")
                    })
                
                df_export = pd.DataFrame(export_data)
                csv = df_export.to_csv(index=False)
                
                st.download_button(
                    label="📥 Descargar resultados (CSV)",
                    data=csv,
                    file_name=f"simit_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
