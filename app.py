from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc
from datetime import datetime
import urllib.parse
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')
# En producción cambia esto por una variable de entorno segura
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cambiar_por_una_clave_segura_en_tests")

# --- Configuración de SQL Server: reemplaza por tus valores de desarrollo/test
# Opciones:
#  - Para autenticación integrada (Windows auth) usa: trusted_connection: True (y NO UID/PWD)
#  - Para SQL auth proporciona UID y PWD y no pongas trusted_connection
SQL_CONFIG = {
    "DRIVER": "ODBC Driver 17 for SQL Server",
    "SERVER": r"CORESLAP\SQLEXPRESS",   # ejemplo: "localhost\\SQLEXPRESS" o "MI_SERVIDOR"
    "DATABASE": "simulacion_db",
    # "UID": "sa",          # descomenta si usas SQL auth
    # "PWD": "tu_password", # descomenta si usas SQL auth
    "trusted_connection": True,
    "autocommit": True
}

PHONE_NUMBER = "+524491449242"  # número tal como lo pediste (sin espacios, con prefijo)

def get_connection():
    # Construye la cadena de conexión dinámicamente según SQL_CONFIG
    parts = []
    parts.append(f"DRIVER={{{SQL_CONFIG['DRIVER']}}}")
    parts.append(f"SERVER={SQL_CONFIG['SERVER']}")
    parts.append(f"DATABASE={SQL_CONFIG['DATABASE']}")

    if SQL_CONFIG.get("trusted_connection"):
        parts.append("Trusted_Connection=yes")
    else:
        # espera que UID y PWD estén presentes
        uid = SQL_CONFIG.get("UID")
        pwd = SQL_CONFIG.get("PWD")
        if not uid or not pwd:
            raise ValueError("UID/PWD requeridos si no usas trusted_connection")
        parts.append(f"UID={uid}")
        parts.append(f"PWD={pwd}")

    conn_str = ";".join(parts)
    conn = pyodbc.connect(conn_str, autocommit=SQL_CONFIG.get("autocommit", False))
    return conn

# Crear tabla (solo usar una vez desde app o desde SSMS)
def ensure_table():
    create_sql = """
    IF OBJECT_ID('dbo.collected_data', 'U') IS NULL
    BEGIN
      CREATE TABLE dbo.collected_data (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(200),
        email NVARCHAR(200),
        method NVARCHAR(50),
        message NVARCHAR(MAX),
        created_at DATETIME2
      );
    END
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(create_sql)
        cur.commit()  # por si autocommit=False
    finally:
        conn.close()

@app.route('/qrpage')
def qr_page():
    return render_template('qr_page.html')

@app.route('/qrsubmit', methods=['POST'])
def qr_submit():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    if not name or not email:
        flash("Por favor completa ambos campos.", "danger")
        return redirect(url_for('qr_page'))

    try:
        store_entry(name, email, "qr_form", f"Formulario QR - Nombre: {name}, Correo: {email}")
    except Exception as e:
        app.logger.error(f"Error al guardar en DB desde QR: {e}")
        flash("Error al guardar los datos.", "danger")
        return redirect(url_for('qr_page'))

    # Redirige para mostrar la animación
    return redirect(url_for('qr_page') + '?done=1')

@app.route('/')
def index():
    # Asegura la tabla en startup (solo en entorno de pruebas)
    try:
        ensure_table()
    except Exception as e:
        # no bloquear la app si no puede crear la tabla; solo informar
        app.logger.warning(f"No se pudo crear/asegurar tabla: {e}")
    return render_template('index.html', phone=PHONE_NUMBER)

def store_entry(name, email, method, message):
    insert_sql = """
    INSERT INTO dbo.collected_data (name, email, method, message, created_at)
    VALUES (?, ?, ?, ?, ?)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(insert_sql, (name, email, method, message, datetime.utcnow()))
        cur.commit()  # por si autocommit=False
    finally:
        conn.close()

@app.route('/submit', methods=['POST'])
def submit():
    # método indica de qué pestaña viene: "sms" o "whatsapp"
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    method = request.form.get('method', 'unknown')
    if not name or not email:
        flash("Por favor rellena nombre y correo.", "danger")
        return redirect(url_for('index') + "#" + method)

    # construir el mensaje que se "simula" enviar
    message = f"Nombre: {name}\nCorreo: {email}\n(simulación: método={method})"

    # Guardar en SQL Server (registro de ejercicio)
    try:
        store_entry(name, email, method, message)
    except Exception as e:
        app.logger.error(f"Error guardando en DB: {e}")
        flash("Error interno guardando los datos (ver logs).", "danger")
        return redirect(url_for('index') + "#" + method)

    # preparar enlaces pre-llenados (cliente debe pulsarlos para enviar realmente)
    # sms:
    sms_body = urllib.parse.quote(message)
    sms_link = f"sms:{PHONE_NUMBER}?body={sms_body}"

    # whatsapp via wa.me (abre app de WhatsApp)
    wa_text = urllib.parse.quote(message)
    wa_link = f"https://wa.me/{PHONE_NUMBER.lstrip('+')}?text={wa_text}"

    flash("Datos guardados en la base de datos de prueba.", "success")

    # Retornar la página con los enlaces para que el usuario haga click manualmente
    return render_template('index.html', phone=PHONE_NUMBER,
                           preview_message=message,
                           sms_link=sms_link,
                           wa_link=wa_link,
                           active_tab=method)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
