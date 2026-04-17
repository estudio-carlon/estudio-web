from flask import Flask, request, redirect, session, send_file
import psycopg2
import os
import pandas as pd
import qrcode
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super_secret_key"
DB_URL = os.getenv("DB_URL")


# ================= DB =================
def conectar():
    return psycopg2.connect(DB_URL)


def init_db():
    conn = conectar()
    c = conn.cursor()

    # USUARIOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY,
        usuario TEXT,
        clave TEXT,
        rol TEXT DEFAULT 'admin',
        cliente_id INTEGER
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

def actualizar_db():
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE clientes ADD COLUMN cuit TEXT")
    except:
        pass
    conn.commit()
    conn.close()


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


def generar_deuda_mensual():
    conn = conectar()
    c = conn.cursor()

    periodo = datetime.now().strftime("%m/%Y")

    c.execute("SELECT id, abono FROM clientes")
    clientes = c.fetchall()

    for cliente_id, abono in clientes:
        c.execute("""
            SELECT id FROM cuentas
            WHERE cliente_id=%s AND periodo=%s
        """, (cliente_id, periodo))

        if not c.fetchone():
            c.execute("""
                INSERT INTO cuentas(cliente_id, periodo, debe, haber)
                VALUES(%s,%s,%s,0)
            """, (cliente_id, periodo, abono or 0))

    conn.commit()
    conn.close()


init_db()
actualizar_db()
limpiar_duplicados()
generar_deuda_mensual()


# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        clave = request.form["clave"]

        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT clave FROM usuarios WHERE usuario=%s", (user,))
        data = c.fetchone()
        conn.close()

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
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT SUM(debe) FROM cuentas")
    total_debe = c.fetchone()[0] or 0

    c.execute("SELECT SUM(haber) FROM cuentas")
    total_haber = c.fetchone()[0] or 0

    deuda = total_debe - total_haber
    conn.close()

    return f"""
    <style>
    body {{ font-family:Arial; background:#f4f6f9; }}
    .card {{ background:white; padding:20px; margin:10px; border-radius:10px; display:inline-block; width:250px; }}
    </style>

    <h1>📊 Panel</h1>

    <div class="card">💰 Facturado<br>${total_debe}</div>
    <div class="card">✅ Cobrado<br>${total_haber}</div>
    <div class="card">🔴 Deuda<br>${deuda}</div>

    <br><br>
    <a href='/clientes'>👥 Clientes</a><br>
    <a href='/deudas'>🔔 Deudores</a>
    """


# ================= CLIENTES =================
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
            INSERT INTO clientes(nombre,telefono,abono)
            VALUES(%s,%s,%s)
        """, (
            request.form["nombre"],
            request.form["telefono"],
            request.form["abono"]
        ))
        conn.commit()

    c.execute("SELECT * FROM clientes ORDER BY nombre")
    data = c.fetchall()

    html = """
    <style>
    body { font-family:Arial; background:#f4f6f9; }
    .container { padding:20px; }
    .card { background:white; padding:15px; margin-bottom:10px; border-radius:10px; }
    .btn { padding:5px 10px; border-radius:5px; text-decoration:none; font-size:12px; margin-right:5px; }
    .azul { background:#007bff; color:white; }
    .amarillo { background:#ffc107; color:black; }
    .rojo { background:#dc3545; color:white; }
    </style>

    <div class="container">
    <h2>👥 Clientes</h2>

    <form method='post'>
        <input name='nombre' placeholder='Nombre'>
        <input name='telefono' placeholder='Teléfono'>
        <input name='abono' placeholder='Abono'>
        <button>Agregar</button>
    </form>
    """

    for d in data:
        html += f"""
        <div class="card">
            <b>{d[1]}</b><br>
            📞 {d[3]} | 💰 ${d[4]}<br><br>

            <a class="btn azul" href="/cuenta/{d[0]}">Cuenta</a>
            <a class="btn amarillo" href="/editar_cliente/{d[0]}">Editar</a>
            <a class="btn rojo" href="/borrar_cliente/{d[0]}" onclick="return confirm('¿Seguro?')">Borrar</a>
        </div>
        """

    html += "</div>"
    conn.close()
    return html


# ================= EDITAR =================
@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
            UPDATE clientes
            SET nombre=%s, telefono=%s, abono=%s
            WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["telefono"],
            request.form["abono"],
            id
        ))
        conn.commit()
        conn.close()
        return redirect("/clientes")

    c.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    d = c.fetchone()
    conn.close()

    return f"""
    <h2>Editar Cliente</h2>
    <form method='post'>
        Nombre:<br><input name='nombre' value='{d[1]}'><br>
        Teléfono:<br><input name='telefono' value='{d[3]}'><br>
        Abono:<br><input name='abono' value='{d[4]}'><br><br>
        <button>Guardar</button>
    </form>
    """


# ================= BORRAR =================
@app.route("/borrar_cliente/<int:id>")
def borrar_cliente(id):
    conn = conectar()
    c = conn.cursor()
    c.execute("DELETE FROM clientes WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/clientes")


# ================= CUENTA =================
@app.route("/cuenta/<int:id>", methods=["GET", "POST"])
def cuenta(id):
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        periodo = request.form["periodo"]
        pago = float(request.form["pago"])

        c.execute("""
            UPDATE cuentas
            SET haber = COALESCE(haber,0) + %s
            WHERE cliente_id=%s AND periodo=%s
        """, (pago, id, periodo))

        conn.commit()

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
        estado = "PAGADO" if saldo <= 0 else f"DEBE ${saldo}"
        
        link_pago = crear_link_pago(saldo, f"Pago {d[0]}")

        c.execute("SELECT telefono FROM clientes WHERE id=%s", (id,))
        tel = c.fetchone()[0] or ""
        telefono = tel.replace(" ", "").replace("+", "")

        mensaje = f"Hola, podés pagar tu periodo {d[0]} por ${saldo}: {link_pago}"
        link = f"https://wa.me/{telefono}?text={mensaje.replace(' ', '%20')}"

        html += f"""
<div>
{d[0]} | {estado}<br>
<a href='/recibo/{id}/{d[0].replace("/", "-")}' target='_blank'>Ver</a> |
<a href='/recibo/{id}/{d[0].replace("/", "-")}?download=1'>Descargar</a> |
<a href='{link_pago}' target='_blank'>💳 Pagar</a> |
<a href='{link}' target='_blank'>WhatsApp</a>
</div><br>
"""
 
    html += """
    <form method='post'>
    Periodo:<input name='periodo'>
    Pago:<input name='pago'>
    <button>Pagar</button>
    </form>
    """

    conn.close()
    return html


# ================= PDF =================
def generar_pdf(cliente_id, periodo, monto):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    conn = conectar()
    c_db = conn.cursor()
    c_db.execute("SELECT nombre, cuit FROM clientes WHERE id=%s", (cliente_id,))
    data = c_db.fetchone()
    cliente = data[0]
    cuit_cliente = data[1] or ""

    # ===== LOGO CENTRADO =====
    if os.path.exists("logo.png"):
        logo = ImageReader("logo.png")
        c.drawImage(logo, width/2 - 60, height - 100, width=120, height=60)

    # ===== TITULO =====
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 120, "RECIBO")

    # ===== NUMERO AUTOMATICO =====
    numero = datetime.now().strftime("%Y%m%d%H%M")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 40, height - 120, f"N° {numero}")

    # ===== FECHA =====
    c.drawRightString(width - 40, height - 140, datetime.now().strftime("%d/%m/%Y"))

    # ===== DATOS EMPRESA =====
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 180, "Estudio Contable Carlon")
    c.drawString(40, height - 195, "Servicios Contables e Impositivos")
    c.drawString(40, height - 210, "CUIT: 27-35045505-7")
    c.drawString(40, height - 225, "Absalón Rojas s/n")
    c.drawString(40, height - 240, "Quimilí, Santiago del Estero - CP 3740")

    # ===== CLIENTE =====
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, height - 280, f"Cliente: {cliente}")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 295, f"CUIT: {cuit_cliente}")
    c.drawString(40, height - 310, f"Periodo: {periodo}")

    # ===== CAJA TOTAL =====
    c.rect(40, height - 370, width - 80, 60)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 335, "TOTAL PAGADO:")

    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(width - 60, height - 335, f"$ {monto}")

    # ===== TEXTO =====
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 400, "Recibí conforme el importe indicado en concepto de honorarios profesionales.")

    # ===== FIRMA =====
    c.line(40, height - 450, 200, height - 450)
    c.drawString(40, height - 465, "Firma")

    c.line(width - 200, height - 450, width - 40, height - 450)
    c.drawString(width - 200, height - 465, "Aclaración")
# ===== DATOS BANCARIOS =====
c.setFont("Helvetica", 9)
c.drawString(40, 120, "Datos para transferencia:")
c.drawString(40, 105, "Titular: Alexis Natasha Carlon")
c.drawString(40, 90, "CUIL: 27-35045505-7")
c.drawString(40, 75, "Banco: Banco Nación")
c.drawString(40, 60, "Cuenta: CA $ 28324201345252")
c.drawString(40, 45, "CBU: 0110420630042013452529")
c.drawString(40, 30, "Alias: ESTUDIO.CONTA.CARLON")
c.setFont("Helvetica-Bold", 10)
c.drawString(width - 160, 160, "Escaneá para pagar")

# ===== QR DE PAGO =====
qr_data = f"""
Transferencia bancaria
Titular: Alexis Natasha Carlon
CUIL: 27-35045505-7
CBU: 0110420630042013452529
Alias: ESTUDIO.CONTA.CARLON
Banco: Nación

Monto: ${monto}
Cliente: {cliente}
Periodo: {periodo}
"""

# ===== QR DE PAGO =====
qr_data = f"""
Transferencia bancaria
Titular: Alexis Natasha Carlon
CUIL: 27-35045505-7
CBU: 0110420630042013452529
Alias: ESTUDIO.CONTA.CARLON
Banco: Nación

Monto: ${monto}
Cliente: {cliente}
Periodo: {periodo}
"""

qr = qrcode.make(qr_data)

qr_buffer = BytesIO()
qr.save(qr_buffer)
qr_buffer.seek(0)

qr_image = ImageReader(qr_buffer)

# Posición del QR
c.drawImage(qr_image, width - 150, 50, width=100, height=100)

c.save()
    buffer.seek(0)
    conn.close()

    return buffer

# ================= LINK =================
def crear_link_pago(monto, descripcion):
    url = "https://api.mercadopago.com/checkout/preferences"

    headers = {
        "Authorization": "Bearer TU_ACCESS_TOKEN"
    }

    data = {
        "items": [
            {
                "title": descripcion,
                "quantity": 1,
                "unit_price": float(monto)
            }
        ]
    }

    r = requests.post(url, json=data, headers=headers)

    if r.status_code == 201:
        return r.json()["init_point"]
    return "#"
# ================= RECIBO =================
@app.route("/recibo/<int:cliente_id>/<path:periodo>")
def ver_recibo(cliente_id, periodo):
    periodo = periodo.replace("-", "/")
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        SELECT debe, haber FROM cuentas
        WHERE cliente_id=%s AND periodo=%s
    """, (cliente_id, periodo))

    data = c.fetchone()
    conn.close()

    if not data:
        return "No hay datos"

    debe = data[0]
    haber = data[1]

    monto = haber if haber > 0 else debe

    pdf = generar_pdf(cliente_id, periodo, monto)

    download = request.args.get("download")

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True if download else False,
        download_name="recibo.pdf"
    )


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
    conn.close()

    html = "<h2>Deudores</h2>"
    for d in data:
        html += f"{d[0]} → ${d[1]}<br>"

    return html


# ================= IMPORTAR =================
@app.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "POST":
        archivo = request.files["archivo"]
        df = pd.read_excel(archivo)

        conn = conectar()
        c = conn.cursor()

        for _, row in df.iterrows():
            c.execute("""
                INSERT INTO clientes(nombre,cuit,telefono,abono)
                VALUES(%s,%s,%s,%s)
            """, (
                row.get("nombre y apellido", ""),
                row.get("cuit", ""),
                row.get("telefono", ""),
                row.get("honorario", 0)
            ))

        conn.commit()
        conn.close()
        return "Importado OK"

    return """
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="archivo">
        <button>Subir</button>
    </form>
    """
