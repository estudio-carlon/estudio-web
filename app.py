from flask import Flask, request, redirect, session
import psycopg2
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secret_key"
DB_URL = os.getenv("DB_URL")


def conectar():
    return psycopg2.connect(DB_URL)

# ================= INIT =================
def init_db():
    conn = conectar()
    c = conn.cursor()

    # USUARIOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY,
        usuario TEXT,
        clave TEXT
    )
    """)

    # CLIENTES 
    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes(
        id SERIAL PRIMARY KEY,
        nombre TEXT,
        cuit TEXT,
        telefono TEXT,
        abono REAL
    )
    """)

    # CUENTAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS cuentas(
        id SERIAL PRIMARY KEY,
        cliente_id INTEGER,
        periodo TEXT,
        debe REAL,
        haber REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        clave = request.form["clave"]

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT clave FROM usuarios WHERE usuario=%s", (user,))
        data = c.fetchone()

        if data and check_password_hash(data[0], clave):
            session["user"] = user
            return redirect("/panel")

    return """
    <h2>Login</h2>
    <form method='post'>
    Usuario: <input name='usuario'><br>
    Clave: <input name='clave' type='password'><br>
    <button>Ingresar</button>
    </form>
    """

# ================= PANEL =================
@app.route("/panel")
def panel():
    return """
    <h1 style='color:#c9a86a'>Estudio Carlon</h1>
    <hr>

    <a href='/clientes'>👥 Clientes</a><br><br>
    <a href='/deudas'>🔔 Deudas</a><br><br>
    <a href='/importar'>📥 Importar Excel</a><br><br>
    """

# ================= CREAR ADMIN =================
@app.route("/crear_admin")
def crear_admin():
    conn = conectar()
    c = conn.cursor()

    hash_pass = generate_password_hash("1234")

    c.execute("INSERT INTO usuarios(usuario,clave) VALUES(%s,%s)",
              ("admin", hash_pass))

    conn.commit()
    conn.close()

    return "Usuario admin creado"

# ================= CLIENTES =================
@app.route("/clientes", methods=["GET","POST"])
def clientes():
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("INSERT INTO clientes(nombre,telefono,abono) VALUES(%s,%s,%s)",
                  (request.form["nombre"], request.form["telefono"], request.form["abono"]))
        conn.commit()

    c.execute("SELECT * FROM clientes")
    data = c.fetchall()

    html = "<h2>Clientes</h2><form method='post'>Nombre:<input name='nombre'> Tel:<input name='telefono'> Abono:<input name='abono'><button>Agregar</button></form><br>"

    for d in data:
        html += f"{d[1]} <a href='/cuenta/{d[0]}'>Cuenta</a><br>"

    return html

# ================= CUENTA =================
@app.route("/cuenta/<int:id>", methods=["GET","POST"])
def cuenta(id):
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        periodo = request.form["periodo"]
        pago = float(request.form["pago"])

        c.execute("SELECT haber FROM cuentas WHERE cliente_id=%s AND periodo=%s",
                  (id, periodo))
        data = c.fetchone()

        if data:
            nuevo = data[0] + pago
            c.execute("UPDATE cuentas SET haber=%s WHERE cliente_id=%s AND periodo=%s",
                      (nuevo, id, periodo))
        else:
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,%s,%s)",
                      (id, periodo, pago, pago))

        conn.commit()
        generar_pdf(id, periodo, pago)

    c.execute("SELECT periodo,debe,haber FROM cuentas WHERE cliente_id=%s", (id,))
    datos = c.fetchall()

    html = "<h2>Cuenta</h2>"

    for d in datos:
        saldo = d[1] - d[2]
        estado = "PAGADO" if saldo <= 0 else "ADEUDA"
        html += f"{d[0]} | {estado} | Debe:{d[1]} Haber:{d[2]}<br>"

    html += """
    <form method='post'>
    Periodo:<input name='periodo'>
    Pago:<input name='pago'>
    <button>Pagar</button>
    </form>
    """

    return html

# ================= PDF =================
def generar_pdf(cliente_id, periodo, monto):
    archivo = f"recibo_{datetime.now().timestamp()}.pdf"
    c = canvas.Canvas(archivo)

    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, 50, 730, width=120, height=60)
    except:
        pass

    c.drawString(200,750,"RECIBO DE PAGO")
    c.drawString(50,650,f"Cliente ID: {cliente_id}")
    c.drawString(50,630,f"Periodo: {periodo}")
    c.drawString(50,610,f"Monto: ${monto}")

    c.save()

# ================= DEUDAS =================
@app.route("/deudas")
def deudas():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        SELECT clientes.nombre, SUM(debe-haber)
        FROM cuentas
        JOIN clientes ON clientes.id = cuentas.cliente_id
        GROUP BY clientes.nombre
        HAVING SUM(debe-haber) > 0
    """)

    data = c.fetchall()

    html = "<h2>🔴 Deudores</h2>"

    for d in data:
        html += f"{d[0]} → ${d[1]}<br>"

    return html


@app.route("/importar", methods=["GET","POST"])
def importar():

    if request.method == "POST":
        archivo = request.files["archivo"]

        df = pd.read_excel(archivo)

        conn = conectar()
        c = conn.cursor()

        for _, row in df.iterrows():
            nombre = row.get("nombre", "")
            cuit = row.get("cuit", "")
            telefono = row.get("telefono", "")
            abono = row.get("abono", 0)

            c.execute("""
                INSERT INTO clientes(nombre, cuit, telefono, abono)
                VALUES(%s,%s,%s,%s)
            """, (nombre, cuit, telefono, abono))

        conn.commit()
        conn.close()

        return """
        ✅ Clientes importados <br><br>
        <a href='/panel'>Volver</a>
        """

    return """
    <h2>📥 Importar Excel</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="archivo">
        <button>Subir</button>
    </form>
    <br><a href='/panel'>← Volver</a>
    """
    # cambio para redeploy
