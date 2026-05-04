from flask import Flask, request, redirect, session, send_file, jsonify
import psycopg2
import os
import pandas as pd
import qrcode
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super_secret_key"
app.config["PROPAGATE_EXCEPTIONS"] = True
DB_URL = os.getenv("DB_URL")


# ─────────────────────────────────────────
#  CSS / DISEÑO BASE
# ─────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --bg:       #F7F5F0;
  --card:     #FFFFFF;
  --primary:  #1A3A2A;
  --accent:   #C8A96E;
  --danger:   #C0392B;
  --success:  #27AE60;
  --warning:  #E67E22;
  --text:     #1C1C1C;
  --muted:    #888;
  --border:   #E4DDD0;
  --radius:   12px;
  --shadow:   0 2px 16px rgba(0,0,0,0.07);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

/* NAV */
nav {
  background: var(--primary);
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15);
}
nav .brand {
  font-family: 'DM Serif Display', serif;
  color: var(--accent);
  font-size: 1.3rem;
  letter-spacing: 0.5px;
}
nav .nav-links a {
  color: rgba(255,255,255,0.75);
  text-decoration: none;
  margin-left: 28px;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color .2s;
}
nav .nav-links a:hover { color: var(--accent); }

/* CONTENEDOR */
.container { max-width: 1100px; margin: 0 auto; padding: 36px 24px; }

/* TÍTULO DE PÁGINA */
.page-title {
  font-family: 'DM Serif Display', serif;
  font-size: 2rem;
  color: var(--primary);
  margin-bottom: 8px;
}
.page-subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 32px; }

/* CARDS ESTADÍSTICAS */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
  margin-bottom: 36px;
}
.stat-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 24px 28px;
  box-shadow: var(--shadow);
  border-left: 4px solid var(--accent);
  position: relative;
  overflow: hidden;
}
.stat-card.cobrado { border-left-color: var(--success); }
.stat-card.deuda   { border-left-color: var(--danger); }
.stat-card .stat-label {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}
.stat-card .stat-value {
  font-family: 'DM Serif Display', serif;
  font-size: 1.8rem;
  color: var(--primary);
}
.stat-card .stat-icon {
  position: absolute; right: 20px; top: 20px;
  font-size: 2.2rem; opacity: 0.12;
}

/* BOTONES */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 20px;
  border-radius: 8px;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  font-size: 0.88rem;
  cursor: pointer;
  border: none;
  text-decoration: none;
  transition: all .2s;
}
.btn-primary  { background: var(--primary); color: #fff; }
.btn-primary:hover { background: #254d38; }
.btn-accent   { background: var(--accent); color: #fff; }
.btn-accent:hover { background: #b8955a; }
.btn-success  { background: var(--success); color: #fff; }
.btn-success:hover { background: #229a52; }
.btn-danger   { background: var(--danger); color: #fff; }
.btn-danger:hover { background: #a93226; }
.btn-outline  {
  background: transparent;
  border: 1.5px solid var(--border);
  color: var(--text);
}
.btn-outline:hover { border-color: var(--primary); color: var(--primary); }
.btn-sm { padding: 5px 12px; font-size: 0.8rem; }
.btn-wa { background: #25D366; color: #fff; }
.btn-wa:hover { background: #1ebe5d; }

/* FORMULARIO */
.form-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 28px;
  box-shadow: var(--shadow);
  margin-bottom: 32px;
}
.form-card h3 {
  font-family: 'DM Serif Display', serif;
  font-size: 1.2rem;
  color: var(--primary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.form-group { display: flex; flex-direction: column; gap: 5px; }
.form-group label { font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.form-group input, .form-group select {
  padding: 10px 14px;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.92rem;
  background: var(--bg);
  transition: border-color .2s;
  outline: none;
}
.form-group input:focus, .form-group select:focus {
  border-color: var(--primary);
  background: #fff;
}

/* BUSCADOR */
.search-bar {
  display: flex; align-items: center; gap: 12px;
  background: var(--card);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 10px 16px;
  margin-bottom: 20px;
  box-shadow: var(--shadow);
}
.search-bar input {
  border: none; background: none; outline: none;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem; width: 100%;
}
.search-bar span { color: var(--muted); }

/* TABLA CLIENTES */
.clients-table {
  background: var(--card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.clients-table table {
  width: 100%; border-collapse: collapse;
}
.clients-table thead tr {
  background: var(--primary);
}
.clients-table thead th {
  color: rgba(255,255,255,0.75);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 14px 16px;
  text-align: left;
}
.clients-table tbody tr {
  border-bottom: 1px solid var(--border);
  transition: background .15s;
}
.clients-table tbody tr:last-child { border-bottom: none; }
.clients-table tbody tr:hover { background: #f9f7f3; }
.clients-table td {
  padding: 13px 16px;
  font-size: 0.9rem;
}
.clients-table td.name { font-weight: 600; color: var(--primary); }
.clients-table td.muted { color: var(--muted); font-size: 0.82rem; }
.clients-table td.actions { white-space: nowrap; }

/* CUENTA / ESTADOS */
.account-grid {
  display: grid; gap: 14px;
}
.account-row {
  background: var(--card);
  border-radius: var(--radius);
  padding: 18px 22px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.account-row .period {
  font-family: 'DM Serif Display', serif;
  font-size: 1.1rem;
  color: var(--primary);
  min-width: 100px;
}
.badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.badge-paid    { background: #d5f5e3; color: #1a7a42; }
.badge-partial { background: #fef3cd; color: #9a6700; }
.badge-debt    { background: #fde8e8; color: #c0392b; }

/* DEUDORES */
.debtors-list { display: grid; gap: 12px; }
.debtor-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 18px 22px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-left: 4px solid var(--danger);
}
.debtor-card .debtor-name { font-weight: 600; color: var(--primary); }
.debtor-card .debtor-amount {
  font-family: 'DM Serif Display', serif;
  font-size: 1.3rem;
  color: var(--danger);
}

/* MODAL PAGO */
.modal-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.45); z-index: 200;
  align-items: center; justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal {
  background: var(--card);
  border-radius: 16px;
  padding: 32px;
  min-width: 340px;
  max-width: 460px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  animation: slideUp .25s ease;
}
@keyframes slideUp {
  from { transform: translateY(30px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}
.modal h3 {
  font-family: 'DM Serif Display', serif;
  font-size: 1.4rem;
  color: var(--primary);
  margin-bottom: 6px;
}
.modal .modal-sub { color: var(--muted); font-size: 0.88rem; margin-bottom: 22px; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }

/* LOGIN */
.login-wrap {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--primary) 0%, #0d1f14 100%);
}
.login-card {
  background: var(--card);
  border-radius: 20px;
  padding: 44px 40px;
  width: 380px;
  box-shadow: 0 24px 80px rgba(0,0,0,0.3);
}
.login-card .login-title {
  font-family: 'DM Serif Display', serif;
  font-size: 1.8rem;
  color: var(--primary);
  text-align: center;
  margin-bottom: 4px;
}
.login-card .login-sub {
  color: var(--muted); font-size: 0.85rem;
  text-align: center; margin-bottom: 30px;
}
.login-card .form-group { margin-bottom: 16px; }

/* FLASH */
.flash {
  padding: 12px 18px; border-radius: 8px;
  margin-bottom: 20px; font-size: 0.9rem; font-weight: 500;
}
.flash-ok  { background: #d5f5e3; color: #1a7a42; }
.flash-err { background: #fde8e8; color: #c0392b; }

/* ACCIONES RÁPIDAS */
.quick-actions {
  display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 32px;
}

/* RESPONSIVE */
@media(max-width: 640px){
  .stats-grid { grid-template-columns: 1fr; }
  .account-row { flex-direction: column; align-items: flex-start; }
  nav .nav-links a { margin-left: 14px; font-size: 0.82rem; }
}
"""

def nav(active=""):
    links = [
        ("/panel",   "Panel"),
        ("/clientes","Clientes"),
        ("/deudas",  "Deudores"),
    ]
    items = ""
    for href, label in links:
        style = 'style="color:var(--accent);"' if active == label else ""
        items += f'<a href="{href}" {style}>{label}</a>'
    return f"""
    <nav>
      <span class="brand">✦ Estudio Contable Carlon</span>
      <div class="nav-links">{items}</div>
    </nav>"""

def page(title, body, active=""):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Estudio Carlon</title>
<style>{CSS}</style>
</head>
<body>
{nav(active)}
<div class="container">
{body}
</div>
</body>
</html>"""

def fmt_pesos(n):
    try:
        return f"${float(n):,.0f}".replace(",", ".")
    except:
        return f"${n}"


# ─────────────────────────────────────────
#  DB
# ─────────────────────────────────────────
def conectar():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY,
        usuario TEXT, clave TEXT,
        rol TEXT DEFAULT 'admin',
        cliente_id INTEGER
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes(
        id SERIAL PRIMARY KEY,
        nombre TEXT, cuit TEXT,
        telefono TEXT, email TEXT, abono REAL
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS cuentas(
        id SERIAL PRIMARY KEY,
        cliente_id INTEGER, periodo TEXT,
        debe REAL, haber REAL
    )""")
    conn.commit()
    conn.close()

def columna_existe(tabla, col):
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (tabla,))
    cols = [x[0] for x in c.fetchall()]
    conn.close()
    return col in cols

def actualizar_db():
    conn = conectar()
    c = conn.cursor()
    for col in ["cuit TEXT", "email TEXT"]:
        try:
            c.execute(f"ALTER TABLE clientes ADD COLUMN {col}")
        except:
            conn.rollback()
    conn.commit()
    conn.close()

def generar_deuda_mensual():
    conn = conectar()
    c = conn.cursor()
    periodo = datetime.now().strftime("%m/%Y")
    c.execute("SELECT id, abono FROM clientes")
    for cid, abono in c.fetchall():
        c.execute("SELECT id FROM cuentas WHERE cliente_id=%s AND periodo=%s", (cid, periodo))
        if not c.fetchone():
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,%s,0)",
                      (cid, periodo, abono or 0))
    conn.commit()
    conn.close()

init_db()
actualizar_db()
generar_deuda_mensual()


# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    error = ""
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
        error = "Usuario o contraseña incorrectos"

    err_html = f'<div class="flash flash-err">{error}</div>' if error else ""
    body = f"""
    <div class="login-wrap">
      <div class="login-card">
        <p class="login-title">Bienvenida</p>
        <p class="login-sub">Estudio Contable Carlon</p>
        {err_html}
        <form method="post">
          <div class="form-group">
            <label>Usuario</label>
            <input name="usuario" placeholder="tu usuario" autocomplete="username">
          </div>
          <div class="form-group">
            <label>Contraseña</label>
            <input name="clave" type="password" placeholder="••••••••" autocomplete="current-password">
          </div>
          <button class="btn btn-primary" style="width:100%;margin-top:8px;justify-content:center;">
            Ingresar →
          </button>
        </form>
      </div>
    </div>
    """
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — Estudio Carlon</title>
<style>{CSS}</style>
</head>
<body>{body}</body>
</html>"""


# ─────────────────────────────────────────
#  PANEL
# ─────────────────────────────────────────
@app.route("/panel")
def panel():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(debe),0) FROM cuentas")
    total_debe  = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(haber),0) FROM cuentas")
    total_haber = c.fetchone()[0]
    deuda = total_debe - total_haber
    c.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT cliente_id) FROM cuentas WHERE (debe-haber)>0")
    total_deudores = c.fetchone()[0]
    conn.close()

    pct = int((total_haber / total_debe * 100)) if total_debe > 0 else 0

    body = f"""
    <h1 class="page-title">Panel General</h1>
    <p class="page-subtitle">Resumen del estado de cuenta del estudio</p>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-label">Total Facturado</div>
        <div class="stat-value">{fmt_pesos(total_debe)}</div>
      </div>
      <div class="stat-card cobrado">
        <div class="stat-icon">✅</div>
        <div class="stat-label">Total Cobrado</div>
        <div class="stat-value">{fmt_pesos(total_haber)}</div>
      </div>
      <div class="stat-card deuda">
        <div class="stat-icon">🔴</div>
        <div class="stat-label">Deuda Pendiente</div>
        <div class="stat-value">{fmt_pesos(deuda)}</div>
      </div>
      <div class="stat-card" style="border-left-color:#7B68EE">
        <div class="stat-icon">👥</div>
        <div class="stat-label">Clientes</div>
        <div class="stat-value">{total_clientes}</div>
      </div>
    </div>

    <div class="form-card" style="margin-bottom:24px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <span style="font-weight:600;color:var(--primary);">Cobrado vs Facturado</span>
        <span style="font-weight:700;color:var(--success);">{pct}%</span>
      </div>
      <div style="background:var(--border);border-radius:6px;height:10px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:var(--success);border-radius:6px;transition:width .5s;"></div>
      </div>
    </div>

    <div class="quick-actions">
      <a href="/clientes" class="btn btn-primary">👥 Ver Clientes</a>
      <a href="/deudas"   class="btn btn-accent">🔔 Ver Deudores ({total_deudores})</a>
      <a href="/clientes" class="btn btn-outline">➕ Nuevo Cliente</a>
    </div>
    """
    return page("Panel", body, "Panel")


# ─────────────────────────────────────────
#  CLIENTES
# ─────────────────────────────────────────
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = conectar()
    c = conn.cursor()

    flash = ""
    if request.method == "POST":
        c.execute("""
            INSERT INTO clientes(nombre,cuit,telefono,email,abono)
            VALUES(%s,%s,%s,%s,%s)
        """, (
            request.form.get("nombre","").strip(),
            request.form.get("cuit","").strip(),
            request.form.get("telefono","").strip(),
            request.form.get("email","").strip(),
            request.form.get("abono", 0) or 0
        ))
        conn.commit()
        flash = '<div class="flash flash-ok">✅ Cliente guardado correctamente</div>'

    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes ORDER BY nombre")
    data = c.fetchall()
    conn.close()

    rows = ""
    for d in data:
        cid, nombre, cuit, tel, email, abono = d
        rows += f"""
        <tr data-search="{nombre.lower()} {(cuit or '').lower()}">
          <td class="name">{nombre}</td>
          <td class="muted">{cuit or '—'}</td>
          <td class="muted">{tel or '—'}</td>
          <td>{fmt_pesos(abono or 0)}</td>
          <td class="actions">
            <a href="/cuenta/{cid}"         class="btn btn-sm btn-primary">📋 Cuenta</a>
            <a href="/editar_cliente/{cid}"  class="btn btn-sm btn-outline">✏️ Editar</a>
            <button onclick="confirmarBorrar({cid}, '{nombre.replace("'","")}')"
                    class="btn btn-sm btn-danger">🗑</button>
          </td>
        </tr>"""

    body = f"""
    <h1 class="page-title">Clientes</h1>
    <p class="page-subtitle">{len(data)} clientes registrados</p>

    {flash}

    <div class="form-card">
      <h3>➕ Nuevo Cliente</h3>
      <form method="post">
        <div class="form-grid">
          <div class="form-group">
            <label>Nombre / Razón Social</label>
            <input name="nombre" placeholder="Ej: García Juan" required>
          </div>
          <div class="form-group">
            <label>CUIT</label>
            <input name="cuit" placeholder="20-12345678-9">
          </div>
          <div class="form-group">
            <label>Teléfono</label>
            <input name="telefono" placeholder="38412345678">
          </div>
          <div class="form-group">
            <label>Email</label>
            <input name="email" type="email" placeholder="cliente@email.com">
          </div>
          <div class="form-group">
            <label>Honorarios Mensuales</label>
            <input name="abono" type="number" placeholder="0">
          </div>
        </div>
        <button class="btn btn-primary">Guardar Cliente</button>
      </form>
    </div>

    <div class="search-bar">
      <span>🔍</span>
      <input id="buscar" placeholder="Buscar por nombre o CUIT..." oninput="filtrar(this.value)">
    </div>

    <div class="clients-table">
      <table>
        <thead>
          <tr>
            <th>Nombre</th><th>CUIT</th><th>Teléfono</th>
            <th>Honorarios</th><th>Acciones</th>
          </tr>
        </thead>
        <tbody id="tabla-clientes">
          {rows}
        </tbody>
      </table>
    </div>

    <!-- Modal confirmar borrado -->
    <div class="modal-overlay" id="modal-borrar">
      <div class="modal">
        <h3>¿Eliminar cliente?</h3>
        <p class="modal-sub" id="modal-nombre-cliente"></p>
        <p style="font-size:0.88rem;color:var(--muted);">
          Esta acción no se puede deshacer. Se eliminarán también todos los registros de cuenta.
        </p>
        <div class="modal-actions">
          <button class="btn btn-outline" onclick="cerrarModal()">Cancelar</button>
          <a id="btn-confirmar-borrar" href="#" class="btn btn-danger">Eliminar</a>
        </div>
      </div>
    </div>

    <script>
    function filtrar(q) {{
      q = q.toLowerCase();
      document.querySelectorAll('#tabla-clientes tr').forEach(function(tr) {{
        tr.style.display = tr.dataset.search.includes(q) ? '' : 'none';
      }});
    }}
    function confirmarBorrar(id, nombre) {{
      document.getElementById('modal-nombre-cliente').textContent = nombre;
      document.getElementById('btn-confirmar-borrar').href = '/borrar_cliente/' + id;
      document.getElementById('modal-borrar').classList.add('active');
    }}
    function cerrarModal() {{
      document.getElementById('modal-borrar').classList.remove('active');
    }}
    document.getElementById('modal-borrar').addEventListener('click', function(e) {{
      if (e.target === this) cerrarModal();
    }});
    </script>
    """
    return page("Clientes", body, "Clientes")


# ─────────────────────────────────────────
#  EDITAR CLIENTE
# ─────────────────────────────────────────
@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
            UPDATE clientes SET nombre=%s,cuit=%s,telefono=%s,email=%s,abono=%s WHERE id=%s
        """, (
            request.form.get("nombre","").strip(),
            request.form.get("cuit","").strip(),
            request.form.get("telefono","").strip(),
            request.form.get("email","").strip(),
            request.form.get("abono", 0) or 0,
            id
        ))
        conn.commit()
        conn.close()
        return redirect("/clientes")

    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes WHERE id=%s", (id,))
    d = c.fetchone()
    conn.close()

    body = f"""
    <a href="/clientes" class="btn btn-outline btn-sm" style="margin-bottom:24px;">← Volver</a>
    <h1 class="page-title">Editar Cliente</h1>
    <p class="page-subtitle">{d[1]}</p>

    <div class="form-card">
      <form method="post">
        <div class="form-grid">
          <div class="form-group">
            <label>Nombre / Razón Social</label>
            <input name="nombre" value="{d[1] or ''}" required>
          </div>
          <div class="form-group">
            <label>CUIT</label>
            <input name="cuit" value="{d[2] or ''}">
          </div>
          <div class="form-group">
            <label>Teléfono</label>
            <input name="telefono" value="{d[3] or ''}">
          </div>
          <div class="form-group">
            <label>Email</label>
            <input name="email" type="email" value="{d[4] or ''}">
          </div>
          <div class="form-group">
            <label>Honorarios Mensuales</label>
            <input name="abono" type="number" value="{d[5] or 0}">
          </div>
        </div>
        <div style="display:flex;gap:10px;">
          <button class="btn btn-primary">Guardar Cambios</button>
          <a href="/clientes" class="btn btn-outline">Cancelar</a>
        </div>
      </form>
    </div>
    """
    return page(f"Editar — {d[1]}", body, "Clientes")


# ─────────────────────────────────────────
#  BORRAR CLIENTE
# ─────────────────────────────────────────
@app.route("/borrar_cliente/<int:id>")
def borrar_cliente(id):
    conn = conectar()
    c = conn.cursor()
    c.execute("DELETE FROM cuentas WHERE cliente_id=%s", (id,))
    c.execute("DELETE FROM clientes WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/clientes")


# ─────────────────────────────────────────
#  CUENTA DE CLIENTE
# ─────────────────────────────────────────
@app.route("/cuenta/<int:id>", methods=["GET", "POST"])
def cuenta(id):
    conn = conectar()
    c = conn.cursor()

    flash = ""
    if request.method == "POST":
        periodo = request.form["periodo"]
        pago    = float(request.form["pago"] or 0)

        # Verificar si existe el registro; si no, crearlo
        c.execute("SELECT id FROM cuentas WHERE cliente_id=%s AND periodo=%s", (id, periodo))
        if c.fetchone():
            c.execute("UPDATE cuentas SET haber=COALESCE(haber,0)+%s WHERE cliente_id=%s AND periodo=%s",
                      (pago, id, periodo))
        else:
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,0,%s)",
                      (id, periodo, pago))
        conn.commit()
        flash = f'<div class="flash flash-ok">✅ Pago de {fmt_pesos(pago)} registrado para {periodo}</div>'

    c.execute("SELECT nombre, cuit, telefono FROM clientes WHERE id=%s", (id,))
    cliente = c.fetchone()
    if not cliente:
        return "Cliente no encontrado", 404
    nombre, cuit, tel = cliente

    c.execute("""
        SELECT periodo, debe, haber FROM cuentas
        WHERE cliente_id=%s ORDER BY
        SUBSTRING(periodo,4,4) DESC,
        SUBSTRING(periodo,1,2) DESC
    """, (id,))
    datos = c.fetchall()
    conn.close()

    # Total deuda del cliente
    total_deuda = sum(max(d[1] - d[2], 0) for d in datos)

    # Filas de cuenta
    filas = ""
    for d in datos:
        saldo = d[1] - d[2]
        if saldo <= 0:
            badge = '<span class="badge badge-paid">✓ PAGADO</span>'
        elif d[2] > 0:
            badge = f'<span class="badge badge-partial">PARCIAL — debe {fmt_pesos(saldo)}</span>'
        else:
            badge = f'<span class="badge badge-debt">DEBE {fmt_pesos(saldo)}</span>'

        telefono = (tel or "").replace(" ","").replace("+","").strip()
        wa_msg   = f"Hola {nombre}, podés pagar el periodo {d[0]} por {fmt_pesos(saldo)} al CBU 0110420630042013452529 Alias: ESTUDIO.CONTA.CARLON"
        wa_link  = f"https://wa.me/{telefono}?text={wa_msg.replace(' ','%20')}" if telefono else "#"
        per_url  = d[0].replace("/", "-")
        monto_mostrar = fmt_pesos(d[2] if d[2] > 0 else d[1])

        btn_pagar = f"""
        <button onclick="abrirPago('{d[0]}', {saldo})"
                class="btn btn-sm btn-success" {'disabled style="opacity:.4"' if saldo<=0 else ''}>
          💳 Registrar Pago
        </button>""" if saldo > 0 else ""

        filas += f"""
        <div class="account-row">
          <span class="period">{d[0]}</span>
          <span>{monto_mostrar}</span>
          {badge}
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a href="/recibo/{id}/{per_url}" target="_blank" class="btn btn-sm btn-outline">📄 Ver</a>
            <a href="/recibo/{id}/{per_url}?download=1"     class="btn btn-sm btn-outline">⬇ PDF</a>
            {btn_pagar}
            {'<a href="'+wa_link+'" target="_blank" class="btn btn-sm btn-wa">📱 WhatsApp</a>' if telefono else ''}
          </div>
        </div>"""

    body = f"""
    <a href="/clientes" class="btn btn-outline btn-sm" style="margin-bottom:24px;">← Clientes</a>

    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:28px;">
      <div>
        <h1 class="page-title">{nombre}</h1>
        <p class="page-subtitle">CUIT: {cuit or '—'} &nbsp;|&nbsp; Tel: {tel or '—'}</p>
      </div>
      <div style="text-align:right;">
        <div style="font-size:0.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;">Deuda Total</div>
        <div style="font-family:'DM Serif Display',serif;font-size:2rem;color:{'var(--danger)' if total_deuda>0 else 'var(--success)'};">
          {fmt_pesos(total_deuda)}
        </div>
      </div>
    </div>

    {flash}

    <div class="account-grid">
      {filas if filas else '<p style="color:var(--muted);text-align:center;padding:32px;">Sin movimientos registrados</p>'}
    </div>

    <!-- Modal Registrar Pago -->
    <div class="modal-overlay" id="modal-pago">
      <div class="modal">
        <h3>💳 Registrar Pago</h3>
        <p class="modal-sub" id="modal-pago-sub"></p>
        <form method="post" id="form-pago">
          <input type="hidden" name="periodo" id="input-periodo">
          <div class="form-group" style="margin-bottom:18px;">
            <label>Monto a acreditar</label>
            <input name="pago" id="input-monto" type="number" step="0.01" required
                   style="font-size:1.2rem;font-weight:600;">
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-outline" onclick="cerrarPago()">Cancelar</button>
            <button type="submit" class="btn btn-success">Confirmar Pago</button>
          </div>
        </form>
      </div>
    </div>

    <script>
    function abrirPago(periodo, saldo) {{
      document.getElementById('modal-pago-sub').textContent = 'Periodo: ' + periodo;
      document.getElementById('input-periodo').value = periodo;
      document.getElementById('input-monto').value = saldo;
      document.getElementById('modal-pago').classList.add('active');
    }}
    function cerrarPago() {{
      document.getElementById('modal-pago').classList.remove('active');
    }}
    document.getElementById('modal-pago').addEventListener('click', function(e) {{
      if (e.target === this) cerrarPago();
    }});
    </script>
    """
    return page(nombre, body, "Clientes")


# ─────────────────────────────────────────
#  DEUDORES
# ─────────────────────────────────────────
@app.route("/deudas")
def deudas():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT clientes.id, clientes.nombre, clientes.telefono,
               SUM(debe-haber) AS deuda
        FROM cuentas
        JOIN clientes ON clientes.id = cuentas.cliente_id
        GROUP BY clientes.id, clientes.nombre, clientes.telefono
        HAVING SUM(debe-haber) > 0
        ORDER BY deuda DESC
    """)
    data = c.fetchall()
    conn.close()

    total = sum(d[3] for d in data)

    cards = ""
    for d in data:
        tel = (d[2] or "").replace(" ","").replace("+","")
        wa = f'<a href="https://wa.me/{tel}?text=Hola%20{d[1].replace(" ","%20")}%2C%20tiene%20deuda%20pendiente%20de%20{fmt_pesos(d[3])}%20con%20el%20Estudio%20Carlon." target="_blank" class="btn btn-sm btn-wa">📱 WhatsApp</a>' if tel else ""
        cards += f"""
        <div class="debtor-card">
          <div>
            <div class="debtor-name">{d[1]}</div>
            <div style="font-size:0.8rem;color:var(--muted);">Tel: {d[2] or '—'}</div>
          </div>
          <div style="display:flex;align-items:center;gap:12px;">
            <span class="debtor-amount">{fmt_pesos(d[3])}</span>
            <a href="/cuenta/{d[0]}" class="btn btn-sm btn-outline">Ver Cuenta</a>
            {wa}
          </div>
        </div>"""

    body = f"""
    <h1 class="page-title">Deudores</h1>
    <p class="page-subtitle">{len(data)} clientes con saldo pendiente — Total: {fmt_pesos(total)}</p>

    <div class="debtors-list">
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:48px;">🎉 Sin deudores pendientes</p>'}
    </div>
    """
    return page("Deudores", body, "Deudores")


# ─────────────────────────────────────────
#  PDF / RECIBO
# ─────────────────────────────────────────
def generar_pdf(cliente_id, periodo, monto):
    buffer = BytesIO()
    cv = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT nombre, cuit FROM clientes WHERE id=%s", (cliente_id,))
    data = c.fetchone()
    conn.close()
    cliente_nombre = data[0] if data else "—"
    cuit_cliente   = data[1] if data else ""

    # Fondo header
    cv.setFillColorRGB(0.10, 0.23, 0.16)
    cv.rect(0, height - 130, width, 130, fill=1, stroke=0)

    # Logo (si existe)
    if os.path.exists("logo.png"):
        logo = ImageReader("logo.png")
        cv.drawImage(logo, 40, height - 115, width=90, height=50, preserveAspectRatio=True, mask="auto")

    # Título en header
    cv.setFillColorRGB(0.78, 0.66, 0.43)
    cv.setFont("Helvetica-Bold", 22)
    cv.drawString(160, height - 60, "RECIBO DE PAGO")

    cv.setFillColorRGB(1, 1, 1)
    cv.setFont("Helvetica", 9)
    cv.drawString(160, height - 80, "Estudio Contable Carlon — Servicios Contables e Impositivos")

    numero = datetime.now().strftime("%Y%m%d%H%M")
    cv.setFont("Helvetica-Bold", 10)
    cv.drawRightString(width - 40, height - 50, f"N° {numero}")
    cv.setFont("Helvetica", 9)
    cv.drawRightString(width - 40, height - 68, datetime.now().strftime("%d/%m/%Y"))

    # Datos empresa
    cv.setFillColorRGB(0.1, 0.1, 0.1)
    cv.setFont("Helvetica-Bold", 9)
    cv.drawString(40, height - 155, "ESTUDIO CONTABLE CARLON")
    cv.setFont("Helvetica", 9)
    cv.drawString(40, height - 170, "CUIT: 27-35045505-7")
    cv.drawString(40, height - 183, "Absalón Rojas s/n — Quimilí, Santiago del Estero — CP 3740")

    # Separador
    cv.setStrokeColorRGB(0.87, 0.87, 0.87)
    cv.line(40, height - 198, width - 40, height - 198)

    # Datos cliente
    cv.setFont("Helvetica-Bold", 9)
    cv.setFillColorRGB(0.53, 0.53, 0.53)
    cv.drawString(40, height - 220, "CLIENTE")
    cv.setFillColorRGB(0.1, 0.1, 0.1)
    cv.setFont("Helvetica-Bold", 13)
    cv.drawString(40, height - 238, cliente_nombre)
    cv.setFont("Helvetica", 9)
    cv.drawString(40, height - 254, f"CUIT: {cuit_cliente or '—'}   |   Periodo: {periodo}")

    # Caja monto
    cv.setFillColorRGB(0.97, 0.96, 0.94)
    cv.roundRect(40, height - 320, width - 80, 54, 8, fill=1, stroke=0)
    cv.setFillColorRGB(0.10, 0.23, 0.16)
    cv.setFont("Helvetica-Bold", 11)
    cv.drawString(58, height - 282, "TOTAL ABONADO")
    cv.setFont("Helvetica-Bold", 22)
    cv.drawRightString(width - 58, height - 282, f"$ {monto:,.0f}".replace(",","."))

    cv.setFont("Helvetica", 8)
    cv.setFillColorRGB(0.4, 0.4, 0.4)
    cv.drawString(40, height - 340, "Recibí conforme el importe indicado en concepto de honorarios profesionales.")

    # Firmas
    cv.setStrokeColorRGB(0.7, 0.7, 0.7)
    cv.line(40,  height - 395, 200, height - 395)
    cv.line(width - 200, height - 395, width - 40, height - 395)
    cv.setFont("Helvetica", 8)
    cv.setFillColorRGB(0.5, 0.5, 0.5)
    cv.drawString(40,  height - 408, "Firma")
    cv.drawString(width - 200, height - 408, "Aclaración")

    # Datos bancarios
    cv.setFillColorRGB(0.97, 0.96, 0.94)
    cv.roundRect(40, 40, (width - 80) * 0.6, 110, 8, fill=1, stroke=0)
    cv.setFillColorRGB(0.10, 0.23, 0.16)
    cv.setFont("Helvetica-Bold", 9)
    cv.drawString(54, 138, "DATOS PARA TRANSFERENCIA")
    cv.setFont("Helvetica", 8.5)
    cv.setFillColorRGB(0.2, 0.2, 0.2)
    for i, line in enumerate([
        "Titular: Alexis Natasha Carlon",
        "CUIL: 27-35045505-7  |  Banco: Nación",
        "Cuenta: CA $ 28324201345252",
        "CBU: 0110420630042013452529",
        "Alias: ESTUDIO.CONTA.CARLON"
    ]):
        cv.drawString(54, 122 - i*14, line)

    # QR
    qr_data = f"CBU:0110420630042013452529\nAlias:ESTUDIO.CONTA.CARLON\nMonto:{monto}\nCliente:{cliente_nombre}\nPeriodo:{periodo}"
    qr = qrcode.make(qr_data)
    qr_buf = BytesIO()
    qr.save(qr_buf)
    qr_buf.seek(0)
    cv.drawImage(ImageReader(qr_buf), width - 155, 38, width=108, height=108)
    cv.setFont("Helvetica-Bold", 8)
    cv.setFillColorRGB(0.10, 0.23, 0.16)
    cv.drawCentredString(width - 101, 33, "Escaneá para pagar")

    cv.save()
    buffer.seek(0)
    return buffer


@app.route("/recibo/<int:cliente_id>/<path:periodo>")
def ver_recibo(cliente_id, periodo):
    periodo = periodo.replace("-", "/")
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT debe, haber FROM cuentas WHERE cliente_id=%s AND periodo=%s", (cliente_id, periodo))
    data = c.fetchone()
    conn.close()
    if not data:
        return "No hay datos para ese período", 404

    monto = data[1] if data[1] > 0 else data[0]
    pdf   = generar_pdf(cliente_id, periodo, monto)
    download = request.args.get("download")
    return send_file(pdf, mimetype="application/pdf",
                     as_attachment=bool(download), download_name="recibo.pdf")


# ─────────────────────────────────────────
#  IMPORTAR EXCEL
# ─────────────────────────────────────────
@app.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "POST":
        archivo = request.files["archivo"]
        df = pd.read_excel(archivo)
        conn = conectar()
        c = conn.cursor()
        for _, row in df.iterrows():
            c.execute("INSERT INTO clientes(nombre,cuit,telefono,abono) VALUES(%s,%s,%s,%s)",
                      (row.get("nombre y apellido",""), row.get("cuit",""),
                       row.get("telefono",""), row.get("honorario", 0)))
        conn.commit()
        conn.close()
        return redirect("/clientes")

    body = """
    <h1 class="page-title">Importar Clientes</h1>
    <p class="page-subtitle">Subí un archivo Excel con columnas: nombre y apellido, cuit, telefono, honorario</p>
    <div class="form-card">
      <form method="post" enctype="multipart/form-data">
        <div class="form-group" style="margin-bottom:16px;">
          <label>Archivo Excel (.xlsx)</label>
          <input type="file" name="archivo" accept=".xlsx">
        </div>
        <button class="btn btn-primary">Importar</button>
      </form>
    </div>
    """
    return page("Importar", body)


if __name__ == "__main__":
    app.run(debug=True)

# ══════════════════════════════════════════════════════
#  ASISTENTE IA v2 — RESPUESTAS PREDEFINIDAS + GOOGLE/AFIP
#  Reemplazar la función nav_html() existente con esta versión
# ══════════════════════════════════════════════════════

# NO necesita API key ni configuración externa
# Reemplazá tu función nav_html() completa con esta:

def nav_html(active=""):
    user = session.get("user", "")
    rol = session.get("rol", "secretaria")
    disp = session.get("display", user)
    links_admin = [("/panel","Panel"),("/clientes","Clientes"),("/deudas","Deudores"),
                   ("/gastos","Gastos"),("/caja","Caja"),("/reportes","Reportes"),
                   ("/agenda","Agenda"),("/usuarios","Usuarios")]
    links_sec = [("/clientes","Clientes"),("/deudas","Deudores"),("/gastos","Gastos"),
                 ("/caja","Caja"),("/agenda","Agenda")]
    links = links_admin if rol == "admin" else links_sec
    items = "".join(f'<a href="{h}" class="{"act" if active==l else ""}">{l}</a>' for h,l in links)
    items += '<a href="/logout" class="logout">Salir</a>'
    badge = f'<span class="rbadge {"admin" if rol=="admin" else "sec"}">{"Admin" if rol=="admin" else "Sec."}</span>'

    asistente_widget = """
<div id="ai-btn" onclick="toggleChat()" style="position:fixed;bottom:24px;right:24px;z-index:1000;width:52px;height:52px;border-radius:50%;background:#1A3A2A;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 16px rgba(0,0,0,0.25)" title="Asistente">
  <span style="font-size:22px">🤖</span>
</div>

<div id="ai-panel" style="display:none;position:fixed;bottom:88px;right:24px;z-index:999;width:370px;max-width:calc(100vw - 32px);background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18);overflow:hidden;flex-direction:column;font-family:'DM Sans',sans-serif">

  <div style="background:#1A3A2A;padding:14px 16px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:10px">
      <div style="width:36px;height:36px;border-radius:50%;background:#C8A96E;display:flex;align-items:center;justify-content:center;font-size:18px">🤖</div>
      <div>
        <div style="color:#fff;font-weight:600;font-size:.9rem">Asistente Estudio Carlon</div>
        <div style="color:rgba(255,255,255,.55);font-size:.72rem">Consultas del sistema y contables</div>
      </div>
    </div>
    <button onclick="toggleChat()" style="background:none;border:none;color:rgba(255,255,255,.7);cursor:pointer;font-size:18px;padding:4px">✕</button>
  </div>

  <div id="ai-msgs" style="height:340px;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#F7F5F0">
    <div style="background:#fff;border-radius:4px 14px 14px 14px;padding:11px 13px;font-size:.83rem;color:#1C1C1C;max-width:90%;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
      ¡Hola! Puedo ayudarte con el sistema o redirigirte a AFIP y Google para consultas contables. ¿Qué necesitás?
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:10px">
        <button class="qbtn" onclick="sendQ('¿Cómo registro un pago?')">💳 Registrar pago</button>
        <button class="qbtn" onclick="sendQ('¿Cómo cierro la caja?')">🗃 Cerrar caja</button>
        <button class="qbtn" onclick="sendQ('¿Cómo agrego un cliente?')">👤 Agregar cliente</button>
        <button class="qbtn" onclick="sendQ('¿Cómo genero un recibo?')">📄 Generar recibo</button>
        <button class="qbtn" onclick="sendQ('Vencimiento IVA')">📅 Vto. IVA</button>
        <button class="qbtn" onclick="sendQ('Cómo presentar declaración jurada')">🧾 DDJJ AFIP</button>
        <button class="qbtn" onclick="sendQ('Monotributo recategorización')">📊 Monotributo</button>
        <button class="qbtn" onclick="sendQ('Ingresos brutos Santiago del Estero')">🏛 IIBB Sgo.</button>
      </div>
    </div>
  </div>

  <div style="padding:10px 12px;background:#fff;border-top:1px solid #E4DDD0;display:flex;gap:8px;align-items:flex-end">
    <textarea id="ai-input" placeholder="Escribí tu consulta..." rows="1"
      style="flex:1;border:1.5px solid #E4DDD0;border-radius:12px;padding:8px 12px;font-family:'DM Sans',sans-serif;font-size:.84rem;resize:none;outline:none;line-height:1.45;max-height:90px;overflow-y:auto;background:#F7F5F0;color:#1C1C1C"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAI()}"
      oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
    <button onclick="sendAI()" style="width:36px;height:36px;border-radius:50%;background:#1A3A2A;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="white"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
    </button>
  </div>
</div>

<style>
.qbtn{background:#F0EDE8;border:1px solid #E4DDD0;border-radius:20px;padding:4px 10px;font-size:.73rem;cursor:pointer;color:#1A3A2A;font-family:'DM Sans',sans-serif}
.qbtn:hover{background:#E4DDD0}
.amsg{background:#fff;border-radius:4px 14px 14px 14px;padding:11px 13px;font-size:.83rem;color:#1C1C1C;max-width:90%;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,0.06);white-space:pre-wrap}
.umsg{background:#1A3A2A;color:#fff;border-radius:14px 4px 14px 14px;padding:10px 13px;font-size:.83rem;max-width:90%;align-self:flex-end;margin-left:auto;line-height:1.55}
.extbtn{display:inline-flex;align-items:center;gap:5px;margin-top:8px;margin-right:5px;padding:5px 11px;border-radius:20px;font-size:.75rem;font-weight:600;cursor:pointer;border:none;text-decoration:none}
.btn-google{background:#4285F4;color:#fff}
.btn-afip{background:#0055a5;color:#fff}
.btn-rentas{background:#1A3A2A;color:#fff}
</style>

<script>
var aiAbierto = false;

var RESP = {
  // ── SISTEMA ──
  "pago": {
    txt: "Para registrar un pago:\n1. Andá a Clientes\n2. Buscá el cliente → tocá 📋 Cuenta\n3. En la fila del período → tocá 💳 Pagar\n4. Ingresá monto, medio de pago y si hay factura ARCA\n5. Tocá Confirmar Pago ✓",
    links: []
  },
  "caja": {
    txt: "Para cerrar la caja del día:\n1. Menú → Caja\n2. Revisá el resumen de cobros del día\n3. Tocá 🔒 Cerrar Caja Hoy\n4. Confirmá\n\nQueda registrado con tu usuario, fecha y hora.",
    links: []
  },
  "cliente": {
    txt: "Para agregar un cliente:\n1. Andá a Clientes\n2. Completá: nombre, CUIT, teléfono, email y honorarios\n3. Tocá Guardar Cliente\n\nEl sistema le crea automáticamente la cuenta del mes actual.",
    links: []
  },
  "recibo": {
    txt: "Para generar un recibo PDF:\n1. Andá a la cuenta del cliente\n2. En el período → tocá 📄 Ver para verlo en pantalla\n3. O tocá ⬇ PDF para descargarlo\n\nEl recibo incluye QR con datos de transferencia.",
    links: []
  },
  "deudor": {
    txt: "Para ver los deudores:\n1. Menú → Deudores\n\nVes la lista completa con el monto de cada uno. Podés enviar WhatsApp directo desde ahí con el mensaje de cobro ya redactado.",
    links: []
  },
  "gasto": {
    txt: "Para registrar un gasto:\n1. Menú → Gastos\n2. Elegí categoría, monto y descripción\n3. Tocá Registrar Gasto\n\nLos gastos se descuentan del rendimiento real en el panel.",
    links: []
  },
  "usuario": {
    txt: "Para crear un usuario (solo admin):\n1. Menú → Usuarios\n2. Completá nombre, usuario, contraseña y rol\n3. Tocá Crear Usuario\n\nRol Secretaria: ve clientes, pagos, caja y agenda.\nRol Admin: acceso completo.",
    links: []
  },
  "agenda": {
    txt: "La agenda de vencimientos está en Menú → Agenda.\n\nAhí podés ver todos los vencimientos del mes y actualizar el estado de cada uno:\n📝 En borrador → ✅ Presentado\n\nTambién podés agregar notas de avance.",
    links: []
  },
  "whatsapp": {
    txt: "Para enviar WhatsApp a un deudor:\n1. Menú → Deudores\n2. En la fila del cliente → tocá 📱 WA\n\nSe abre WhatsApp con el mensaje ya redactado incluyendo el monto y los datos bancarios del estudio.",
    links: []
  },
  "secretaria": {
    txt: "Las secretarias pueden:\n✓ Ver y agregar clientes\n✓ Registrar pagos\n✓ Ver deudores\n✓ Registrar gastos\n✓ Caja diaria\n✓ Agenda de vencimientos\n\nNo tienen acceso a: panel financiero, reportes ni usuarios.",
    links: []
  },

  // ── CONTABLES / IMPOSITIVOS → redirigen a AFIP o Google ──
  "iva": {
    txt: "Para presentar la declaración jurada de IVA necesitás el aplicativo SIAP o usar el servicio web de AFIP. Te llevo directo a la información oficial:",
    links: [
      {label:"🏛 IVA en AFIP", url:"https://www.afip.gob.ar/iva/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=como+presentar+declaracion+jurada+IVA+AFIP+Argentina", cls:"btn-google"}
    ]
  },
  "ddjj": {
    txt: "Para presentar declaraciones juradas en AFIP podés usar el portal web o el aplicativo SIAP. Te llevo a la información oficial:",
    links: [
      {label:"🏛 Declaraciones en AFIP", url:"https://www.afip.gob.ar/declaraciones/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=como+presentar+declaracion+jurada+AFIP+Argentina+paso+a+paso", cls:"btn-google"}
    ]
  },
  "monotributo": {
    txt: "Para consultas sobre Monotributo, recategorización y pagos te llevo directo a AFIP:",
    links: [
      {label:"🏛 Monotributo AFIP", url:"https://www.afip.gob.ar/monotributo/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=monotributo+recategorizacion+2025+AFIP+Argentina", cls:"btn-google"}
    ]
  },
  "iibb": {
    txt: "Para Ingresos Brutos de Santiago del Estero, los trámites se gestionan en la Dirección General de Rentas provincial:",
    links: [
      {label:"🏛 Rentas Sgo. del Estero", url:"https://www.rentas.sde.gov.ar", cls:"btn-rentas"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=ingresos+brutos+Santiago+del+Estero+vencimientos+2025", cls:"btn-google"}
    ]
  },
  "ganancias": {
    txt: "Para consultas sobre el impuesto a las Ganancias, anticipos y deducciones:",
    links: [
      {label:"🏛 Ganancias en AFIP", url:"https://www.afip.gob.ar/gananciasybienes/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=impuesto+ganancias+anticipos+AFIP+Argentina+2025", cls:"btn-google"}
    ]
  },
  "aportes": {
    txt: "Para aportes y contribuciones (F.931) y empleados en relación de dependencia:",
    links: [
      {label:"🏛 SUSS / F.931 en AFIP", url:"https://www.afip.gob.ar/suss/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=formulario+931+aportes+contribuciones+AFIP+como+presentar", cls:"btn-google"}
    ]
  },
  "factura": {
    txt: "Para emitir facturas electrónicas usás el portal ARCA (antes AFIP):",
    links: [
      {label:"🧾 Ir a ARCA / Facturación", url:"https://www.afip.gob.ar/facturacion/", cls:"btn-afip"},
      {label:"🔍 Cómo facturar en ARCA", url:"https://www.google.com/search?q=como+emitir+factura+electronica+ARCA+AFIP+2025", cls:"btn-google"}
    ]
  },
  "vencimiento": {
    txt: "Para ver el calendario completo de vencimientos impositivos de AFIP:",
    links: [
      {label:"🏛 Vencimientos AFIP", url:"https://www.afip.gob.ar/institucional/estudios/vencimientos.asp", cls:"btn-afip"},
      {label:"📅 Ver Agenda del estudio", url:"/agenda", cls:"btn-rentas"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=vencimientos+AFIP+2025+calendario+impositivo", cls:"btn-google"}
    ]
  },
  "bienes": {
    txt: "Para consultas sobre Bienes Personales y sus declaraciones:",
    links: [
      {label:"🏛 Bienes Personales AFIP", url:"https://www.afip.gob.ar/gananciasybienes/", cls:"btn-afip"},
      {label:"🔍 Buscar en Google", url:"https://www.google.com/search?q=bienes+personales+declaracion+jurada+AFIP+2025", cls:"btn-google"}
    ]
  }
};

function classify(q) {
  q = q.toLowerCase();
  if(/pago|cobr|registr.*pago|cómo.*pago/.test(q)) return "pago";
  if(/caja|cerrar.*caja|cierre/.test(q)) return "caja";
  if(/cliente|agreg|nuevo.*cliente/.test(q)) return "cliente";
  if(/recibo|pdf|comprobante/.test(q)) return "recibo";
  if(/deudor|deuda|debe/.test(q)) return "deudor";
  if(/gasto|egreso/.test(q)) return "gasto";
  if(/usuario|secretaria|permiso|rol/.test(q)) return "usuario";
  if(/agenda|vencimiento.*agenda/.test(q)) return "agenda";
  if(/whatsapp|wa|mensaje/.test(q)) return "whatsapp";
  if(/iva|valor agregado/.test(q)) return "iva";
  if(/ddjj|declaraci|jurada/.test(q)) return "ddjj";
  if(/monotributo|monotrib|recategor/.test(q)) return "monotributo";
  if(/ingresos brutos|iibb|brutos/.test(q)) return "iibb";
  if(/ganancia/.test(q)) return "ganancias";
  if(/aporte|contribuci|f\.?931|suss|empleado|sueldo/.test(q)) return "aportes";
  if(/factur|arca|comprobante electr/.test(q)) return "factura";
  if(/vencimiento|vence|fecha.*imp/.test(q)) return "vencimiento";
  if(/bien.*personal|bienes/.test(q)) return "bienes";
  if(/secretaria|qué puedo|mis permisos/.test(q)) return "secretaria";
  return null;
}

function addMsg(txt, tipo, links) {
  var box = document.getElementById('ai-msgs');
  var d = document.createElement('div');
  d.className = tipo === 'user' ? 'umsg' : 'amsg';
  d.textContent = txt;
  if(links && links.length) {
    var ldiv = document.createElement('div');
    links.forEach(function(l) {
      var a = document.createElement('a');
      a.href = l.url;
      a.textContent = l.label;
      a.className = 'extbtn ' + l.cls;
      if(!l.url.startsWith('/')) a.target = '_blank';
      ldiv.appendChild(a);
    });
    d.appendChild(ldiv);
  }
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

function sendQ(q) {
  document.getElementById('ai-input').value = q;
  sendAI();
}

function sendAI() {
  var inp = document.getElementById('ai-input');
  var q = inp.value.trim();
  if(!q) return;
  inp.value = ''; inp.style.height = 'auto';
  addMsg(q, 'user', null);

  var key = classify(q);
  setTimeout(function() {
    if(key && RESP[key]) {
      addMsg(RESP[key].txt, 'bot', RESP[key].links);
    } else {
      addMsg('No tengo esa respuesta guardada. Te abro Google para que puedas buscar:', 'bot', [
        {label:'🔍 Buscar en Google', url:'https://www.google.com/search?q='+encodeURIComponent(q+' Argentina contable impositivo'), cls:'btn-google'},
        {label:'🏛 Ir a AFIP', url:'https://www.afip.gob.ar', cls:'btn-afip'}
      ]);
    }
  }, 500);
}

function toggleChat() {
  aiAbierto = !aiAbierto;
  var p = document.getElementById('ai-panel');
  p.style.display = aiAbierto ? 'flex' : 'none';
  if(aiAbierto) setTimeout(function(){ document.getElementById('ai-input').focus(); }, 100);
}
</script>
"""
    return f'<nav><span class="brand">✦ Estudio Carlon</span><div class="nav-links">{items}</div><div class="user-pill">👤 {disp} {badge}</div></nav>{asistente_widget}'

