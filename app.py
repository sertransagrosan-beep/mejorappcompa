import requests
import streamlit as st
import time
from datetime import datetime
import pandas as pd

# Configuración
URL_API = "https://consultasimit.fcm.org.co/simit/microservices/estado-cuenta-simit/estadocuenta/consulta"
TIEMPO_ESPERA = 30  # segundos entre consultas

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.fcm.org.co",
    "Referer": "https://www.fcm.org.co/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def consultar_comparendo(cedula):
    """Consulta un comparendo por número de cédula"""
    
    session = requests.Session()
    
    # El payload SOLO usa la cédula, no la placa
    payload = {
        "filtro": str(cedula),  # Solo la cédula
        "reCaptchaDTO": {
            "response": f"{{\"time\":{int(time.time())},\"nonce\":\"\"}}"
        }
    }
    
    try:
        response = session.post(URL_API, json=payload, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data}
        elif response.status_code == 429:
            return {"success": False, "error": "Demasiadas consultas. Espera 30 segundos."}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "detail": response.text}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def consultar_multiples(cedulas, progreso_callback=None):
    """Consulta múltiples cédulas respetando el tiempo de espera"""
    resultados = []
    
    for idx, cedula in enumerate(cedulas):
        if progreso_callback:
            progreso_callback(idx, len(cedulas), cedula)
        
        resultado = consultar_comparendo(cedula)
        resultados.append({
            "cedula": cedula,
            "timestamp": datetime.now().isoformat(),
            "resultado": resultado
        })
        
        # Esperar 30 segundos antes de la siguiente consulta (excepto la última)
        if idx < len(cedulas) - 1:
            time.sleep(TIEMPO_ESPERA)
    
    return resultados

# ============ APLICACIÓN STREAMLIT ============
st.set_page_config(page_title="Consultor SIMIT", page_icon="🚗")
st.title("🚗 Consultor de Comparendos SIMIT")
st.markdown("Consulta el estado de cuenta de un conductor por su número de cédula")

# Sidebar con información
with st.sidebar:
    st.header("ℹ️ Información")
    st.info(f"""
    **Límites del sistema:**
    - ⏱️ {TIEMPO_ESPERA} segundos entre consultas
    - 📋 Máximo 25 cédulas por lote
    - ⏰ Una consulta masiva toma ~{TIEMPO_ESPERA * 25 / 60:.0f} minutos
    """)
    
    st.markdown("---")
    st.markdown("### 💡 Importante")
    st.success("""
    La consulta se realiza SOLO con el número de cédula.
    No es necesario ingresar la placa del vehículo.
    """)

# Modo de consulta única
with st.expander("🔍 Consulta individual", expanded=True):
    with st.form("consulta_unica"):
        cedula = st.text_input("Número de cédula", placeholder="Ej: 74370314")
        
        submitted = st.form_submit_button("Consultar", type="primary")
        
        if submitted:
            if not cedula:
                st.error("❌ Ingresa un número de cédula")
            else:
                with st.spinner("Consultando SIMIT..."):
                    resultado = consultar_comparendo(cedula)
                
                if resultado.get("success"):
                    st.success("✅ Consulta exitosa")
                    
                    # Mostrar datos bonitos
                    data = resultado["data"]
                    st.json(data)
                    
                    # Intentar extraer información relevante si existe
                    if isinstance(data, dict):
                        if "deudaTotal" in data:
                            st.metric("💰 Deuda total", f"${data['deudaTotal']:,.0f}")
                        if "comparendos" in data:
                            st.metric("📋 Comparendos", len(data['comparendos']) if isinstance(data['comparendos'], list) else "N/A")
                else:
                    st.error(f"❌ Error: {resultado.get('error')}")

# Modo de consulta masiva
with st.expander("📊 Consulta masiva (hasta 25 cédulas)"):
    st.markdown("**Formato:** una cédula por línea")
    
    ejemplo = """74370314
98765432
55555555"""
    
    cedulas_input = st.text_area("Lista de cédulas:", ejemplo, height=150)
    
    # Opciones
    col1, col2 = st.columns([3, 1])
    with col1:
        iniciar = st.button("🚀 Iniciar consulta masiva", type="primary", use_container_width=True)
    with col2:
        guardar_csv = st.checkbox("Guardar resultados en CSV", value=True)
    
    if iniciar:
        # Parsear input
        cedulas = [linea.strip() for linea in cedulas_input.strip().split('\n') if linea.strip()]
        
        if len(cedulas) == 0:
            st.error("❌ No se encontraron cédulas válidas")
        elif len(cedulas) > 25:
            st.error(f"❌ Máximo 25 cédulas. Tienes {len(cedulas)}.")
        else:
            # Confirmación
            st.warning(f"""
            ⚠️ **Vas a consultar {len(cedulas)} cédulas**
            
            Tiempo estimado: {len(cedulas) * TIEMPO_ESPERA / 60:.1f} minutos
            ¿Deseas continuar?
            """)
            
            if st.button("✅ Sí, continuar"):
                # Barra de progreso
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def actualizar_progreso(idx, total, cedula):
                    porcentaje = (idx + 1) / total
                    progress_bar.progress(porcentaje)
                    status_text.markdown(f"""
                    **Consultando:** {idx+1}/{total}
                    - 📝 Cédula: `{cedula}`
                    - ⏳ Esperando {TIEMPO_ESPERA}s entre consultas...
                    """)
                
                # Ejecutar consultas
                resultados = consultar_multiples(cedulas, actualizar_progreso)
                
                # Mostrar resultados
                status_text.markdown("✅ **¡Consultas completadas!**")
                st.balloons()
                
                # Tabla de resumen
                resumen_data = []
                for r in resultados:
                    resumen_data.append({
                        "Cédula": r["cedula"],
                        "Estado": "✅ Éxito" if r["resultado"].get("success") else "❌ Error",
                        "Mensaje": r["resultado"].get("error", "Consulta exitosa")[:50] if not r["resultado"].get("success") else "OK"
                    })
                
                df_resumen = pd.DataFrame(resumen_data)
                st.dataframe(df_resumen, use_container_width=True)
                
                # Exportar resultados
                if guardar_csv:
                    # Exportar resultados completos
                    export_data = []
                    for r in resultados:
                        export_data.append({
                            "cedula": r["cedula"],
                            "fecha_consulta": r["timestamp"],
                            "exito": r["resultado"].get("success"),
                            "datos": str(r["resultado"].get("data")) if r["resultado"].get("success") else None,
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
                
                # Mostrar detalles expandibles
                with st.expander("📋 Ver resultados detallados"):
                    for r in resultados:
                        if r["resultado"].get("success"):
                            st.success(f"✅ Cédula {r['cedula']}")
                            st.json(r["resultado"]["data"])
                        else:
                            st.error(f"❌ Cédula {r['cedula']}: {r['resultado'].get('error')}")
                        st.divider()

# Instrucciones
with st.expander("📖 Guía rápida"):
    st.markdown("""
    ### Cómo usar esta herramienta
    
    1. **Ingresa el número de cédula** del conductor
    2. **Haz clic en Consultar**
    3. **Espera la respuesta** (puede tomar unos segundos)
    
    ### ¿Por qué no necesito la placa?
    
    El sistema SIMIT asocia los comparendos directamente al número de cédula del conductor, no al vehículo. Al consultar por cédula, obtienes **todos los comparendos** de esa persona, independientemente del vehículo.
    
    ### Consulta masiva
    
    Para consultar varios conductores:
    - Ingresa una cédula por línea
    - La app esperará 30 segundos entre cada consulta
    - Los resultados se pueden descargar en CSV o JSON
    
    ### Solución de problemas
    
    | Problema | Solución |
    |----------|----------|
    | Error "Demasiadas consultas" | Espera 30 segundos y reintenta |
    | La consulta falla | Verifica que la cédula sea correcta |
    | Resultado vacío | El conductor podría no tener comparendos |
    """)
