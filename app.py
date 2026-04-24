import requests
import streamlit as st
import time
from datetime import datetime
import pandas as pd
import json

# Configuración
URL_API = "https://consultasimit.fcm.org.co/simit/microservices/estado-cuenta-simit/estadocuenta/consulta"
URL_INICIO = "https://www.fcm.org.co/simit/"
TIEMPO_ESPERA = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Origin": "https://www.fcm.org.co",
    "Referer": "https://www.fcm.org.co/",
    "Content-Type": "application/json",
}

def obtener_sesion():
    """Obtiene una sesión válida con cookies"""
    session = requests.Session()
    
    # Primero visita la página principal para obtener cookies
    try:
        response_inicio = session.get(URL_INICIO, headers=HEADERS, timeout=30)
        
        # También intenta con la página de estado-cuenta
        session.get("https://www.fcm.org.co/simit/#/estado-cuenta", headers=HEADERS, timeout=30)
        
        # Esperar un momento para que se procesen las cookies
        time.sleep(2)
        
        return session
    except Exception as e:
        st.error(f"Error obteniendo sesión: {e}")
        return None

def consultar_comparendo(cedula, session=None):
    """Consulta un comparendo por número de cédula usando una sesión válida"""
    
    if session is None:
        session = obtener_sesion()
        if session is None:
            return {"success": False, "error": "No se pudo establecer sesión"}
    
    # Payload solo con la cédula
    payload = {
        "filtro": str(cedula),
        "reCaptchaDTO": {
            "response": f"{{\"time\":{int(time.time())},\"nonce\":\"\"}}"
        }
    }
    
    try:
        response = session.post(URL_API, json=payload, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data}
        elif response.status_code == 401:
            return {"success": False, "error": "Error de autenticación. Intenta abrir la página del SIMIT primero en tu navegador."}
        elif response.status_code == 429:
            return {"success": False, "error": "Demasiadas consultas. Espera 30 segundos."}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "detail": response.text}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def consultar_multiples(cedulas, progreso_callback=None):
    """Consulta múltiples cédulas usando la misma sesión"""
    
    # Obtener una sesión válida al inicio
    session = obtener_sesion()
    if session is None:
        return [{"cedula": c, "resultado": {"success": False, "error": "No se pudo establecer sesión"}} for c in cedulas]
    
    resultados = []
    
    for idx, cedula in enumerate(cedulas):
        if progreso_callback:
            progreso_callback(idx, len(cedulas), cedula)
        
        resultado = consultar_comparendo(cedula, session)
        resultados.append({
            "cedula": cedula,
            "timestamp": datetime.now().isoformat(),
            "resultado": resultado
        })
        
        if idx < len(cedulas) - 1:
            time.sleep(TIEMPO_ESPERA)
    
    return resultados

# ============ APLICACIÓN STREAMLIT ============
st.set_page_config(page_title="Consultor SIMIT", page_icon="🚗")
st.title("🚗 Consultor de Comparendos SIMIT")
st.markdown("Consulta el estado de cuenta de un conductor por su número de cédula")

# Advertencia importante
st.warning("""
⚠️ **IMPORTANTE:** Por favor, abre esta página en una pestaña separada antes de consultar:
[https://www.fcm.org.co/simit/#/estado-cuenta](https://www.fcm.org.co/simit/#/estado-cuenta)

Esto es necesario para establecer una sesión válida.
""")

with st.sidebar:
    st.header("ℹ️ Información")
    st.info(f"""
    **Límites del sistema:**
    - ⏱️ {TIEMPO_ESPERA} segundos entre consultas
    - 📋 Máximo 25 cédulas por lote
    """)
    
    if st.button("🔄 Verificar conexión"):
        with st.spinner("Probando conexión con SIMIT..."):
            session = obtener_sesion()
            if session:
                st.success("✅ Conexión exitosa")
            else:
                st.error("❌ No se pudo conectar")

# Modo de consulta única
with st.expander("🔍 Consulta individual", expanded=True):
    cedula = st.text_input("Número de cédula", placeholder="Ej: 74370314")
    
    if st.button("Consultar", type="primary"):
        if not cedula:
            st.error("❌ Ingresa un número de cédula")
        else:
            with st.spinner("Consultando SIMIT..."):
                resultado = consultar_comparendo(cedula)
            
            if resultado.get("success"):
                st.success("✅ Consulta exitosa")
                
                data = resultado["data"]
                
                # Mostrar datos formateados
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        for comparendo in data["data"]:
                            with st.container():
                                st.markdown(f"**📄 Comparendo:** {comparendo.get('numeroComparendo', 'N/A')}")
                                st.markdown(f"**💰 Valor:** ${comparendo.get('valor', 'N/A'):,.0f}")
                                st.markdown(f"**📅 Fecha:** {comparendo.get('fecha', 'N/A')}")
                                st.divider()
                    else:
                        st.json(data)
                else:
                    st.json(data)
            else:
                st.error(f"❌ Error: {resultado.get('error')}")
                if "detail" in resultado and resultado["detail"]:
                    st.code(resultado["detail"])

# Modo de consulta masiva
with st.expander("📊 Consulta masiva (hasta 25 cédulas)"):
    st.markdown("**Formato:** una cédula por línea")
    
    ejemplo = """74370314
98765432
55555555"""
    
    cedulas_input = st.text_area("Lista de cédulas:", ejemplo, height=150)
    
    if st.button("🚀 Iniciar consulta masiva", type="primary"):
        cedulas = [linea.strip() for linea in cedulas_input.strip().split('\n') if linea.strip()]
        
        if len(cedulas) == 0:
            st.error("❌ No se encontraron cédulas válidas")
        elif len(cedulas) > 25:
            st.error(f"❌ Máximo 25 cédulas. Tienes {len(cedulas)}.")
        else:
            st.warning(f"⚠️ Vas a consultar {len(cedulas)} cédulas. Tiempo estimado: {len(cedulas) * TIEMPO_ESPERA / 60:.1f} minutos")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def actualizar_progreso(idx, total, cedula):
                progress_bar.progress((idx + 1) / total)
                status_text.markdown(f"**Consultando:** {idx+1}/{total} - Cédula: `{cedula}`")
            
            with st.spinner("Consultando..."):
                resultados = consultar_multiples(cedulas, actualizar_progreso)
            
            status_text.markdown("✅ **¡Consultas completadas!**")
            st.balloons()
            
            # Mostrar resumen
            for r in resultados:
                if r["resultado"].get("success"):
                    st.success(f"✅ Cédula {r['cedula']}")
                else:
                    st.error(f"❌ Cédula {r['cedula']}: {r['resultado'].get('error')}")
            
            # Descargar resultados
            resultados_json = json.dumps(resultados, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Descargar resultados (JSON)",
                data=resultados_json,
                file_name=f"simit_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
