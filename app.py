from flask import Flask, request, redirect, session, send_file
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
def actualizar_db():
    conn = conectar()
    c = conn.cursor()

    try:
        c.execute("ALTER TABLE clientes ADD COLUMN cuit TEXT")
    except:
        pass

    conn.commit()
    conn.close()

actualizar_db()
def limpiar_duplicados():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        DELETE FROM clientes
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM clientes
            GROUP BY nombre
        )
    """)

    conn.commit()
    conn.close()

limpiar_duplicados()
def generar_deuda_mensual():
    conn = conectar()
    c = conn.cursor()

    from datetime import datetime
    periodo = datetime.now().strftime("%m/%Y")

    # Traer todos los clientes
    c.execute("SELECT id, abono FROM clientes")
    clientes = c.fetchall()

    for cliente_id, abono in clientes:

        # Verificar si ya existe ese mes
        c.execute("""
            SELECT id FROM cuentas
            WHERE cliente_id=%s AND periodo=%s
        """, (cliente_id, periodo))

        existe = c.fetchone()

        if not existe:
            c.execute("""
                INSERT INTO cuentas(cliente_id, periodo, debe, haber)
                VALUES(%s,%s,%s,0)
            """, (cliente_id, periodo, abono))

    conn.commit()
    conn.close()

generar_deuda_mensual()
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

    c.execute("""
        SELECT periodo,debe,haber 
        FROM cuentas 
        WHERE cliente_id=%s 
        ORDER BY periodo DESC
    """, (id,))
    datos = c.fetchall()

    html = "<h2>Cuenta</h2>"

    for d in datos:
        saldo = d[1] - d[2]

        if saldo <= 0:
            estado = "✅ PAGADO"
        else:
            estado = f"🔴 DEBE ${saldo}"

        telefono = ""  # después lo mejoramos
        mensaje = f"Hola, te recordamos que tenés pendiente el periodo {d[0]} por un total de ${saldo}"
        link = f"https://wa.me/{telefono}?text={mensaje.replace(' ', '%20')}"

        html += f"""
        {d[0]} | {estado} | Debe:{d[1]} Haber:{d[2]}
        <a href='/recibo/{id}/{d[0]}'>🧾 Recibo</a> |
        <a href='{link}' target='_blank'>📲 WhatsApp</a><br>
        """

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
    conn = conectar()
    c_db = conn.cursor()

    # Traer nombre del cliente
    c_db.execute("SELECT nombre FROM clientes WHERE id=%s", (cliente_id,))
    cliente = c_db.fetchone()[0]

    # Generar número de recibo automático
    c_db.execute("SELECT COUNT(*) FROM cuentas")
    nro = c_db.fetchone()[0]

    archivo = f"recibo_{cliente_id}_{periodo}.pdf"

    c = canvas.Canvas(archivo)

# ================= LOGO =================
from reportlab.lib.utils import ImageReader
import os

if os.path.exists("logo.png"):
    logo = ImageReader("logo.png")
    c.drawImage(logo, 50, 740, width=120, height=60)

# ================= TITULO =================
c.setFont("Helvetica-Bold", 12)
c.drawString(200, 780, "ESTUDIO CARLON")

c.setFont("Helvetica-Bold", 16)
c.drawString(200, 760, "RECIBO DE PAGO")

# Línea decorativa
c.line(40, 730, 550, 730)

# ================= DATOS =================
from datetime import datetime

c.setFont("Helvetica", 11)
c.drawString(50, 700, f"N° Recibo: {nro}")
c.drawString(50, 680, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
c.drawString(50, 650, f"Cliente: {cliente}")
c.drawString(50, 630, f"Periodo: {periodo}")

# ================= MONTO =================
c.setFont("Helvetica-Bold", 14)
c.drawString(50, 590, f"Monto pagado: ${monto}")

# Caja alrededor del monto
c.rect(45, 570, 500, 40)

# ================= FIRMA =================
c.setFont("Helvetica", 10)
c.drawString(50, 520, "________")
c.drawString(50, 505, "Firma")

  c.save()

  conn.close()

  return archivo
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
            nombre = row.get("nombre y apellido", "")
            cuit = row.get("cuit", "")
            telefono = row.get("telefono", "")
            abono = row.get("honorario", 0)

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
from io import BytesIO

@app.route("/recibo/<int:cliente_id>/<path:periodo>")
def ver_recibo(cliente_id, periodo):

    conn = conectar()
    c = conn.cursor()

    # Traer datos del cliente
    c.execute("""
        SELECT nombre FROM clientes WHERE id=%s
    """, (cliente_id,))
    cliente = c.fetchone()[0]

    # Traer monto
    c.execute("""
        SELECT haber FROM cuentas
        WHERE cliente_id=%s AND periodo=%s
    """, (cliente_id, periodo))

    data = c.fetchone()
    monto = data[0] if data else 0

    # Crear PDF en memoria
    buffer = BytesIO()
    c_pdf = canvas.Canvas(buffer)

    # ===== LOGO (opcional) =====
    try:
        logo = ImageReader("logo.png")  # subí un logo al proyecto
        c_pdf.drawImage(logo, 50, 730, width=100, height=50)
    except:
        pass

    # ===== TITULO =====
    c_pdf.setFont("Helvetica-Bold", 18)
    c_pdf.drawString(180, 750, "RECIBO DE PAGO")

    # ===== DATOS EMPRESA =====
    c_pdf.setFont("Helvetica", 10)
    c_pdf.drawString(50, 700, "Estudio Carlon")
    c_pdf.drawString(50, 685, "CUIT: 20-XXXXXXXX-X")

    # ===== DATOS RECIBO =====
    c_pdf.drawString(350, 700, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    c_pdf.drawString(350, 685, f"Periodo: {periodo}")

    # ===== CLIENTE =====
    c_pdf.setFont("Helvetica-Bold", 12)
    c_pdf.drawString(50, 640, f"Cliente: {cliente}")

    # ===== MONTO =====
    c_pdf.setFont("Helvetica-Bold", 14)
    c_pdf.drawString(50, 600, f"Importe abonado: ${monto}")

    # ===== CAJA =====
    c_pdf.rect(45, 580, 500, 80)

    # ===== FIRMA =====
    c_pdf.setFont("Helvetica", 10)
    c_pdf.drawString(50, 520, "________")
    c_pdf.drawString(50, 505, "Firma")

    c_pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=False   # 👈 abre en navegador
    )
    # cambio para redeploy
