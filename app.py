from flask import Flask, request, redirect, session, send_file
import psycopg2, os, qrcode
import json
import urllib.request
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = "estudio_carlon_secret_2025"
app.config["PROPAGATE_EXCEPTIONS"] = True
DB_URL = os.getenv("DB_URL")

MEDIOS_PAGO = ["Transferencia → Natasha Carlon","Transferencia → Maira Carlon",
               "Efectivo","Cheque","Dólares","Otro"]
CATEGORIAS_GASTO = ["Sueldo","Luz","Internet","Tarjetas","Gastos de Oficina",
                    "Artículos de Limpieza","Papelería","Otros"]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');
:root{--bg:#F7F5F0;--card:#fff;--primary:#1A3A2A;--accent:#C8A96E;--danger:#C0392B;--success:#27AE60;--warning:#E67E22;--info:#2475B0;--purple:#7B68EE;--text:#1C1C1C;--muted:#888;--border:#E4DDD0;--r:12px;--shadow:0 2px 18px rgba(0,0,0,0.07)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
nav{background:var(--primary);padding:0 28px;display:flex;align-items:center;justify-content:space-between;height:62px;position:sticky;top:0;z-index:200;box-shadow:0 2px 14px rgba(0,0,0,0.2)}
.brand{font-family:'DM Serif Display',serif;color:var(--accent);font-size:1.18rem;white-space:nowrap}
.nav-links{display:flex;align-items:center;gap:2px;flex-wrap:wrap}
.nav-links a{color:rgba(255,255,255,.72);text-decoration:none;padding:6px 11px;border-radius:7px;font-size:.82rem;font-weight:500;transition:all .18s}
.nav-links a:hover,.nav-links a.act{background:rgba(255,255,255,.11);color:#fff}
.nav-links a.logout{color:rgba(255,120,120,.85)}
.nav-links a.logout:hover{background:rgba(192,57,43,.22);color:#ffaaaa}
.user-pill{background:rgba(255,255,255,.1);border-radius:20px;padding:4px 12px;font-size:.76rem;color:rgba(255,255,255,.82);display:flex;align-items:center;gap:6px;white-space:nowrap}
.rbadge{font-size:.64rem;font-weight:700;padding:2px 7px;border-radius:10px;text-transform:uppercase;letter-spacing:.4px}
.rbadge.admin{background:var(--accent);color:#fff}.rbadge.sec{background:#2475B0;color:#fff}
.wrap{max-width:1180px;margin:0 auto;padding:32px 20px}
.page-title{font-family:'DM Serif Display',serif;font-size:1.9rem;color:var(--primary);margin-bottom:5px}
.page-sub{color:var(--muted);font-size:.84rem;margin-bottom:26px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:24px}
.scard{background:var(--card);border-radius:var(--r);padding:18px 22px;box-shadow:var(--shadow);border-left:4px solid var(--accent);position:relative;overflow:hidden;transition:transform .18s}
.scard:hover{transform:translateY(-2px)}
.scard.g{border-left-color:var(--success)}.scard.r{border-left-color:var(--danger)}.scard.b{border-left-color:var(--info)}.scard.o{border-left-color:var(--warning)}.scard.p{border-left-color:var(--purple)}
.slabel{font-size:.68rem;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:7px}
.sval{font-family:'DM Serif Display',serif;font-size:1.65rem;color:var(--primary)}
.sicon{position:absolute;right:14px;top:12px;font-size:1.8rem;opacity:.1}
.btn{display:inline-flex;align-items:center;gap:5px;padding:8px 17px;border-radius:8px;font-family:'DM Sans',sans-serif;font-weight:600;font-size:.84rem;cursor:pointer;border:none;text-decoration:none;transition:all .18s;white-space:nowrap}
.btn-p{background:var(--primary);color:#fff}.btn-p:hover{background:#254d38}
.btn-a{background:var(--accent);color:#fff}.btn-a:hover{background:#b8955a}
.btn-g{background:var(--success);color:#fff}.btn-g:hover{background:#1f9149}
.btn-r{background:var(--danger);color:#fff}.btn-r:hover{background:#a93226}
.btn-b{background:var(--info);color:#fff}.btn-b:hover{background:#1a5e8a}
.btn-o{background:transparent;border:1.5px solid var(--border);color:var(--text)}.btn-o:hover{border-color:var(--primary);color:var(--primary)}
.btn-wa{background:#25D366;color:#fff}.btn-wa:hover{background:#1ebe5d}
.btn-arca{background:#0055a5;color:#fff}.btn-arca:hover{background:#004080}
.btn-sm{padding:5px 10px;font-size:.77rem}.btn-xs{padding:3px 8px;font-size:.71rem}
.fcard{background:var(--card);border-radius:var(--r);padding:22px;box-shadow:var(--shadow);margin-bottom:22px}
.fcard h3{font-family:'DM Serif Display',serif;font-size:1.1rem;color:var(--primary);margin-bottom:15px;padding-bottom:10px;border-bottom:1px solid var(--border)}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:15px}
.fg{display:flex;flex-direction:column;gap:4px}
.fg label{font-size:.7rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.fg input,.fg select,.fg textarea{padding:9px 11px;border:1.5px solid var(--border);border-radius:8px;font-family:'DM Sans',sans-serif;font-size:.88rem;background:var(--bg);transition:border-color .18s;outline:none}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:var(--primary);background:#fff}
.search{display:flex;align-items:center;gap:9px;background:var(--card);border:1.5px solid var(--border);border-radius:10px;padding:8px 14px;margin-bottom:14px;box-shadow:var(--shadow)}
.search input{border:none;background:none;outline:none;font-family:'DM Sans',sans-serif;font-size:.9rem;width:100%}
.dtable{background:var(--card);border-radius:var(--r);box-shadow:var(--shadow);overflow:hidden;margin-bottom:22px}
.dtable table{width:100%;border-collapse:collapse}
.dtable thead tr{background:var(--primary)}
.dtable thead th{color:rgba(255,255,255,.72);font-size:.68rem;font-weight:600;letter-spacing:.8px;text-transform:uppercase;padding:11px 14px;text-align:left}
.dtable tbody tr{border-bottom:1px solid var(--border);transition:background .13s}
.dtable tbody tr:last-child{border-bottom:none}
.dtable tbody tr:hover{background:#f9f7f3}
.dtable td{padding:10px 14px;font-size:.85rem;vertical-align:middle}
.dtable td.nm{font-weight:600;color:var(--primary)}.dtable td.mu{color:var(--muted);font-size:.78rem}
.arow{background:var(--card);border-radius:var(--r);padding:14px 18px;box-shadow:var(--shadow);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:9px;margin-bottom:10px}
.period{font-family:'DM Serif Display',serif;font-size:1rem;color:var(--primary);min-width:78px}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:.71rem;font-weight:700;letter-spacing:.3px}
.bp{background:#d5f5e3;color:#1a7a42}.bpar{background:#fef3cd;color:#9a6700}.bd{background:#fde8e8;color:#c0392b}
.badm{background:var(--accent);color:#fff}.bsec{background:#dce8ff;color:#1a4a8a}
.bmedio{background:#f0f4ff;color:#2475B0;font-size:.68rem;padding:2px 8px;border-radius:10px;font-weight:600}
.dcard{background:var(--card);border-radius:var(--r);padding:14px 18px;box-shadow:var(--shadow);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:9px;border-left:4px solid var(--danger);margin-bottom:9px}
.dname{font-weight:600;color:var(--primary)}.damt{font-family:'DM Serif Display',serif;font-size:1.15rem;color:var(--danger)}
.logrow{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:.8rem;align-items:flex-start}
.logrow:last-child{border-bottom:none}
.log-time{color:var(--muted);white-space:nowrap;min-width:120px;font-size:.72rem}
.log-user{font-weight:600;color:var(--primary);min-width:72px}
.log-msg{color:var(--text);flex:1}
.log-dot{width:7px;height:7px;border-radius:50%;background:var(--accent);margin-top:5px;flex-shrink:0}
.mo{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:300;align-items:center;justify-content:center}
.mo.on{display:flex}
.modal{background:var(--card);border-radius:16px;padding:26px;min-width:300px;max-width:500px;width:94%;box-shadow:0 20px 60px rgba(0,0,0,.22);animation:su .22s ease;max-height:90vh;overflow-y:auto}
@keyframes su{from{transform:translateY(26px);opacity:0}to{transform:none;opacity:1}}
.modal h3{font-family:'DM Serif Display',serif;font-size:1.25rem;color:var(--primary);margin-bottom:5px}
.modal .msub{color:var(--muted);font-size:.82rem;margin-bottom:16px}
.mact{display:flex;gap:9px;justify-content:flex-end;margin-top:16px}
.progwrap{background:var(--border);border-radius:6px;height:8px;overflow:hidden}
.progbar{height:100%;background:var(--success);border-radius:6px;transition:width .5s}
.chartrow{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.78rem}
.chartrow .cl{width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.chartrow .cbg{flex:1;background:var(--border);border-radius:4px;height:7px}
.chartrow .cfill{height:100%;background:var(--accent);border-radius:4px}
.chartrow .cv{width:82px;text-align:right;color:var(--muted);font-size:.74rem}
.ucard{background:var(--card);border-radius:var(--r);padding:14px 18px;box-shadow:var(--shadow);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:9px;border-left:4px solid var(--info);margin-bottom:9px}
.ucard.adm{border-left-color:var(--accent)}
.flash{padding:10px 15px;border-radius:8px;margin-bottom:14px;font-size:.85rem;font-weight:500}
.fok{background:#d5f5e3;color:#1a7a42}.ferr{background:#fde8e8;color:#c0392b}.finfo{background:#dce8ff;color:#1a4a8a}
.lwrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,var(--primary) 0%,#0d1f14 100%)}
.lcard{background:var(--card);border-radius:20px;padding:38px 34px;width:360px;box-shadow:0 24px 80px rgba(0,0,0,.3)}
.ltitle{font-family:'DM Serif Display',serif;font-size:1.65rem;color:var(--primary);text-align:center;margin-bottom:4px}
.lsub{color:var(--muted);font-size:.8rem;text-align:center;margin-bottom:24px}
.denied{text-align:center;padding:80px 24px}
.denied .di{font-size:3.5rem;margin-bottom:14px}
.denied h2{font-family:'DM Serif Display',serif;font-size:1.75rem;color:var(--primary);margin-bottom:10px}
.denied p{color:var(--muted);margin-bottom:22px}
.tabs{display:flex;gap:3px;margin-bottom:18px;border-bottom:2px solid var(--border)}
.tab{padding:8px 16px;cursor:pointer;font-weight:600;font-size:.84rem;color:var(--muted);border-radius:8px 8px 0 0;transition:all .18s;border:none;background:none;font-family:'DM Sans',sans-serif}
.tab.on{color:var(--primary);border-bottom:2px solid var(--primary);margin-bottom:-2px;background:var(--card)}
.tabpanel{display:none}.tabpanel.on{display:block}
.qa{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}
.info-box{background:#f0f9f4;border:1px solid #b7dfcc;border-radius:8px;padding:10px 14px;font-size:.81rem;color:#1a5c3a;margin-bottom:12px}
.warn-box{background:#fef9ec;border:1px solid #f0d080;border-radius:8px;padding:10px 14px;font-size:.81rem;color:#7a5800;margin-bottom:12px}
.partner-card{background:var(--card);border-radius:var(--r);padding:18px 22px;box-shadow:var(--shadow);text-align:center}
.partner-name{font-family:'DM Serif Display',serif;font-size:1.05rem;color:var(--primary);margin-bottom:6px}
.partner-amt{font-family:'DM Serif Display',serif;font-size:1.9rem;margin-bottom:4px}
.chart-svg{width:100%;overflow:visible}
.caja-row{background:var(--card);border-radius:var(--r);padding:14px 18px;box-shadow:var(--shadow);margin-bottom:10px;border-left:4px solid var(--success)}
.caja-row.cerrada{border-left-color:var(--muted);opacity:.85}
.caja-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.caja-user{font-weight:700;color:var(--primary);font-size:.96rem}
.caja-fecha{font-size:.76rem;color:var(--muted)}
.caja-medios{display:flex;gap:8px;flex-wrap:wrap}
.caja-item{display:flex;flex-direction:column;align-items:center;background:var(--bg);border-radius:8px;padding:8px 14px;min-width:90px;border:1px solid var(--border)}
.caja-item .ci-label{font-size:.68rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px}
.caja-item .ci-val{font-family:'DM Serif Display',serif;font-size:1.1rem;color:var(--primary)}
.caja-item.efectivo{border-color:#27AE60;background:#f0faf4}.caja-item.efectivo .ci-val{color:#1a7a42}
.caja-item.cheque{border-color:#E67E22;background:#fef9f0}.caja-item.cheque .ci-val{color:#a85e00}
.caja-item.dolares{border-color:#2475B0;background:#f0f4ff}.caja-item.dolares .ci-val{color:#1a4a8a}
.caja-item.transferencia{border-color:#7B68EE;background:#f5f3ff}.caja-item.transferencia .ci-val{color:#5a4fcf}
.caja-item.total-fisico{border-color:var(--primary);background:#f0f5f2;border-width:2px}.caja-item.total-fisico .ci-val{color:var(--primary);font-size:1.3rem}
.estado-abierta{display:inline-flex;align-items:center;gap:5px;background:#d5f5e3;color:#1a7a42;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700}
.estado-cerrada{display:inline-flex;align-items:center;gap:5px;background:#f0f0f0;color:#666;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700}
.recibo-badge{display:inline-flex;align-items:center;gap:4px;background:#fff3cd;color:#856404;padding:2px 8px;border-radius:10px;font-size:.69rem;font-weight:600}
@media(max-width:680px){.stats{grid-template-columns:1fr 1fr}.arow{flex-direction:column;align-items:flex-start}nav .user-pill{display:none}.wrap{padding:18px 12px}.nav-links a{padding:5px 8px;font-size:.78rem}.caja-medios{gap:5px}.caja-item{min-width:75px;padding:6px 10px}}
"""

      ASISTENTE IA v2 — RESPUESTAS PREDEFINIDAS + GOOGLE/AFIP

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

def page(title,body,active=""):
    return f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — Estudio Carlon</title><style>{CSS}</style></head><body>{nav_html(active)}<div class="wrap">{body}</div></body></html>'

def fmt(n):
    try: return f"${float(n):,.0f}".replace(",",".")
    except: return f"${n}"

def now_ar(): return datetime.now().strftime("%d/%m/%Y %H:%M")

def denied():
    b='<div class="denied"><div class="di">🔒</div><h2>Acceso restringido</h2><p>No tenés permiso para esta sección.</p><a href="/clientes" class="btn btn-p">← Volver</a></div>'
    return page("Acceso denegado",b),403

def login_req(f):
    @wraps(f)
    def w(*a,**kw):
        if not session.get("user"): return redirect("/")
        return f(*a,**kw)
    return w

def admin_req(f):
    @wraps(f)
    def w(*a,**kw):
        if not session.get("user"): return redirect("/")
        if session.get("rol")!="admin": return denied()
        return f(*a,**kw)
    return w

def conectar(): return psycopg2.connect(DB_URL)

def init_db():
    conn=conectar();c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios(id SERIAL PRIMARY KEY,usuario TEXT UNIQUE,clave TEXT,rol TEXT DEFAULT 'secretaria',nombre_display TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS clientes(id SERIAL PRIMARY KEY,nombre TEXT,cuit TEXT,telefono TEXT,email TEXT,abono REAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS cuentas(id SERIAL PRIMARY KEY,cliente_id INTEGER,periodo TEXT,debe REAL DEFAULT 0,haber REAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS pagos(id SERIAL PRIMARY KEY,cliente_id INTEGER,periodo TEXT,monto REAL,medio TEXT,observaciones TEXT,facturado BOOLEAN DEFAULT FALSE,fecha TEXT,usuario TEXT,emitido_por TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id SERIAL PRIMARY KEY,fecha TEXT,categoria TEXT,descripcion TEXT,monto REAL,usuario TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS auditoria(id SERIAL PRIMARY KEY,fecha TEXT,usuario TEXT,accion TEXT,detalle TEXT,cliente_id INTEGER,cliente_nombre TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS cierres_caja(
        id SERIAL PRIMARY KEY,
        fecha TEXT,
        usuario TEXT,
        efectivo REAL DEFAULT 0,
        cheque REAL DEFAULT 0,
        dolares REAL DEFAULT 0,
        transferencia_nat REAL DEFAULT 0,
        transferencia_mai REAL DEFAULT 0,
        otro REAL DEFAULT 0,
        total_fisico REAL DEFAULT 0,
        total_general REAL DEFAULT 0,
        detalle_pagos TEXT,
        cerrado BOOLEAN DEFAULT FALSE,
        hora_cierre TEXT
    )""")
INIT_AGENDA_SQL = """
    c.execute('''CREATE TABLE IF NOT EXISTS agenda_vencimientos(
        id SERIAL PRIMARY KEY,
        vencimiento_id TEXT,
        mes INTEGER,
        anio INTEGER,
        estado TEXT DEFAULT 'pendiente',
        nota TEXT DEFAULT '',
        usuario TEXT,
        fecha_actualizacion TEXT,
        UNIQUE(vencimiento_id, mes, anio)
    )''')
"""
  conn.commit();conn.close()

def actualizar_db():
    conn=conectar();c=conn.cursor()
    for ddl in ["ALTER TABLE clientes ADD COLUMN IF NOT EXISTS email TEXT","ALTER TABLE clientes ADD COLUMN IF NOT EXISTS abono REAL DEFAULT 0","ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_display TEXT","ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT DEFAULT 'secretaria'","ALTER TABLE auditoria ADD COLUMN IF NOT EXISTS cliente_nombre TEXT","ALTER TABLE pagos ADD COLUMN IF NOT EXISTS observaciones TEXT","ALTER TABLE pagos ADD COLUMN IF NOT EXISTS facturado BOOLEAN DEFAULT FALSE","ALTER TABLE pagos ADD COLUMN IF NOT EXISTS emitido_por TEXT"]:
        try: c.execute(ddl)
        except: conn.rollback()
    conn.commit();conn.close()

def generar_deuda_mensual():
    conn=conectar();c=conn.cursor()
    periodo=datetime.now().strftime("%m/%Y")
    c.execute("SELECT id,abono FROM clientes")
    for cid,abono in c.fetchall():
        c.execute("SELECT id FROM cuentas WHERE cliente_id=%s AND periodo=%s",(cid,periodo))
        if not c.fetchone():
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,%s,0)",(cid,periodo,abono or 0))
    conn.commit();conn.close()

def registrar_auditoria(accion,detalle,cliente_id=None,cliente_nombre=""):
    try:
        conn=conectar();c=conn.cursor()
        c.execute("INSERT INTO auditoria(fecha,usuario,accion,detalle,cliente_id,cliente_nombre) VALUES(%s,%s,%s,%s,%s,%s)",(now_ar(),session.get("display",session.get("user","?")),accion,detalle,cliente_id,cliente_nombre))
        conn.commit();conn.close()
    except: pass

def svg_barras(datos,color="#C8A96E"):
    if not datos: return '<p style="color:var(--muted);font-size:.84rem">Sin datos aún</p>'
    W,H=400,150;mx=max(v for _,v in datos) or 1;n=len(datos)
    gap=int(W/n);bw=int(gap*0.6)
    bars=labels=vals=""
    for i,(per,val) in enumerate(datos):
        x=int(i*gap+gap*0.2);bh=int(val/mx*(H-30));y=H-20-bh
        bars+=f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="3" fill="{color}" opacity=".85"/>'
        labels+=f'<text x="{x+bw//2}" y="{H-4}" text-anchor="middle" font-size="9" fill="#888">{per}</text>'
        if val>0: vals+=f'<text x="{x+bw//2}" y="{y-4}" text-anchor="middle" font-size="8" fill="{color}" font-weight="600">{fmt(val)}</text>'
    return f'<svg viewBox="0 0 {W} {H}" class="chart-svg">{bars}{labels}{vals}</svg>'

init_db();actualizar_db();generar_deuda_mensual()

@app.route("/",methods=["GET","POST"])
def login():
    error=""
    if request.method=="POST":
        user=request.form.get("usuario","").strip();clave=request.form.get("clave","")
        conn=conectar();c=conn.cursor()
        c.execute("SELECT clave,rol,nombre_display FROM usuarios WHERE usuario=%s",(user,))
        data=c.fetchone();conn.close()
        if data and check_password_hash(data[0],clave):
            session["user"]=user;session["rol"]=data[1] or "secretaria";session["display"]=data[2] or user
            registrar_auditoria("LOGIN","Inicio de sesión")
            return redirect("/panel" if session["rol"]=="admin" else "/clientes")
        error="Usuario o contraseña incorrectos"
    err=f'<div class="flash ferr">{error}</div>' if error else ""
    return f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ingresar</title><style>{CSS}</style></head><body><div class="lwrap"><div class="lcard"><p class="ltitle">Bienvenida</p><p class="lsub">Estudio Contable Carlon · Quimilí</p>{err}<form method="post"><div class="fg" style="margin-bottom:12px"><label>Usuario</label><input name="usuario" placeholder="tu usuario" autocomplete="username"></div><div class="fg" style="margin-bottom:18px"><label>Contraseña</label><input name="clave" type="password" placeholder="••••••••" autocomplete="current-password"></div><button class="btn btn-p" style="width:100%;justify-content:center">Ingresar →</button></form></div></div></body></html>'

@app.route("/logout")
def logout():
    registrar_auditoria("LOGOUT","Cierre de sesión");session.clear();return redirect("/")

@app.route("/panel")
@login_req
def panel():
    if session.get("rol")!="admin": return redirect("/clientes")
    conn=conectar();c=conn.cursor()

    # ── Totales generales ──
    c.execute("SELECT COALESCE(SUM(debe),0) FROM cuentas");         td  = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(haber),0) FROM cuentas");        th  = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clientes");                      nc  = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT cliente_id) FROM cuentas WHERE (debe-haber)>0"); nd = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos");         tg  = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Natasha%'"); cobro_nat = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Maira%'");   cobro_mai = c.fetchone()[0]

    # ── Alertas ──
    anio_actual = datetime.now().strftime("%Y")
    # Clientes con 2+ meses sin pagar
    c.execute("""SELECT COUNT(DISTINCT cliente_id) FROM cuentas
                 WHERE (debe-haber)>0
                 AND SUBSTRING(periodo,4,4)=%s""", (anio_actual,))
    n_morosos = c.fetchone()[0]
    # Clientes sin honorario
    c.execute("SELECT COUNT(*) FROM clientes WHERE abono IS NULL OR abono=0")
    n_sin_abono = c.fetchone()[0]
    # Cierres de caja pendientes hoy
    hoy = datetime.now().strftime("%d/%m/%Y")
    c.execute("SELECT COUNT(DISTINCT usuario) FROM pagos WHERE fecha LIKE %s", (f"%{hoy}%",))
    sec_cobraron = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT usuario) FROM cierres_caja WHERE fecha=%s AND cerrado=TRUE", (hoy,))
    sec_cerraron = c.fetchone()[0]
    cajas_pendientes = max(0, sec_cobraron - sec_cerraron)

    # ── Gráfico 1: Ingresos vs Gastos últimos 8 meses ──
    c.execute("""SELECT periodo, COALESCE(SUM(haber),0) FROM cuentas
                 GROUP BY periodo
                 ORDER BY SUBSTRING(periodo,4,4) DESC, SUBSTRING(periodo,1,2) DESC LIMIT 8""")
    raw_ing = list(reversed(c.fetchall()))
    periodos   = [r[0] for r in raw_ing]
    ingresos_m = [float(r[1]) for r in raw_ing]

    gastos_m = []
    for per in periodos:
        c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE fecha LIKE %s", (f"%{per.split('/')[1]}%",))
        gastos_m.append(float(c.fetchone()[0]))

    # ── Gráfico 2: Medios de pago ──
    c.execute("SELECT medio, COALESCE(SUM(monto),0) FROM pagos GROUP BY medio ORDER BY SUM(monto) DESC")
    medios_raw = c.fetchall()
    total_med = sum(float(r[1]) for r in medios_raw) or 1
    medios_labels = [r[0] for r in medios_raw]
    medios_data   = [round(float(r[1])/total_med*100, 1) for r in medios_raw]

    # ── Gráfico 3: Socias por mes ──
    nat_m, mai_m = [], []
    for per in periodos:
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE periodo=%s AND medio ILIKE '%%Natasha%%'", (per,))
        nat_m.append(float(c.fetchone()[0]))
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE periodo=%s AND medio ILIKE '%%Maira%%'", (per,))
        mai_m.append(float(c.fetchone()[0]))

    # ── Gráfico 4: Gastos por categoría ──
    c.execute("SELECT categoria, COALESCE(SUM(monto),0) FROM gastos GROUP BY categoria ORDER BY SUM(monto) DESC LIMIT 7")
    gastos_cat = c.fetchall()
    gcat_labels = [r[0] for r in gastos_cat]
    gcat_data   = [float(r[1]) for r in gastos_cat]

  VENCIMIENTOS_IMPOSITIVOS = [
    {"id": "ib_cat_a",   "nombre": "Ingresos Brutos — Categoría A",   "dia": 18, "tipo": "IIBB Sgo. del Estero", "detalle": "Categoría A · Ingresos Brutos · vence el 18 de cada mes"},
    {"id": "ib_cat_b",   "nombre": "Ingresos Brutos — Categoría B",   "dia": 15, "tipo": "IIBB Sgo. del Estero", "detalle": "Categoría B · Ingresos Brutos · vence el 15 de cada mes"},
    {"id": "iva_ddjj",   "nombre": "IVA — Declaración Jurada (F.731)","dia": 20, "tipo": "AFIP",                  "detalle": "Formulario 731 / SIAP · presentación mensual · fecha según CUIT"},
    {"id": "f931_1",     "nombre": "Aportes y Contribuciones F.931",  "dia": 9,  "tipo": "AFIP",                  "detalle": "Sueldos y jornales — 1ra quincena · SUSS · vence el 9"},
    {"id": "f931_2",     "nombre": "Aportes y Contribuciones F.931",  "dia": 11, "tipo": "AFIP",                  "detalle": "Sueldos y jornales — 2da quincena · SUSS · vence el 11"},
    {"id": "ganancias",  "nombre": "Ganancias — Anticipo mensual",    "dia": 23, "tipo": "AFIP",                  "detalle": "Anticipo según cronograma AFIP — aproximado día 23"},
    {"id": "monotributo","nombre": "Monotributo — Cuota mensual",     "dia": 20, "tipo": "AFIP",                  "detalle": "Cuota unificada mensual — todos los contribuyentes"},
    {"id": "suss_ddjj",  "nombre": "SUSS — Declaración Jurada",       "dia": 9,  "tipo": "AFIP",                  "detalle": "Sistema Único de Seguridad Social · F.931 mensual"},
    {"id": "rentas_prov","nombre": "Rentas Provinciales — Anticipo",  "dia": 20, "tipo": "Rentas SGO",            "detalle": "Dirección General de Rentas · Santiago del Estero"},
]
    # ── Gráfico 5: Rendimiento acumulado ──
    cum_ing, cum_gas = [], []
    si, sg = 0.0, 0.0
    for i in range(len(ingresos_m)):
        si += ingresos_m[i]; sg += gastos_m[i]
        cum_ing.append(round(si)); cum_gas.append(round(sg))

    # ── Top deudores ──
    c.execute("""SELECT cl.nombre, SUM(cu.debe-cu.haber) d FROM cuentas cu
                 JOIN clientes cl ON cl.id=cu.cliente_id
                 GROUP BY cl.nombre HAVING SUM(cu.debe-cu.haber)>0 ORDER BY d DESC LIMIT 6""")
    top = c.fetchall()

    # ── Actividad reciente ──
    c.execute("SELECT fecha,usuario,accion,detalle,cliente_nombre FROM auditoria ORDER BY id DESC LIMIT 8")
    actividad = c.fetchall()
    conn.close()

    deuda=td-th; rend=th-tg; pct=int(th/td*100) if td>0 else 0
    total_s=cobro_nat+cobro_mai
    pct_nat=int(cobro_nat/total_s*100) if total_s>0 else 50; pct_mai=100-pct_nat

    # ── HTML alertas ──
    alertas=""
    if n_sin_abono>0:
        alertas+=f'<div style="background:#fef9ec;border:1px solid #f0d080;border-radius:8px;padding:9px 14px;font-size:.82rem;color:#7a5800;margin-bottom:8px">⚠️ <b>{n_sin_abono}</b> clientes sin honorario asignado · <a href="/clientes" style="color:#7a5800;font-weight:600">Ver clientes →</a></div>'
    if cajas_pendientes>0:
        alertas+=f'<div style="background:#fde8e8;border:1px solid #f5a0a0;border-radius:8px;padding:9px 14px;font-size:.82rem;color:#7a1a1a;margin-bottom:8px">🔴 <b>{cajas_pendientes}</b> secretaria(s) cobraron hoy y aún no cerraron su caja · <a href="/caja" style="color:#7a1a1a;font-weight:600">Ver caja →</a></div>'

    # ── HTML deudores ──
    mx_deu=top[0][1] if top else 1
    barras_deu="".join(f'<div class="chartrow"><span class="cl" title="{n}">{n}</span><div class="cbg"><div class="cfill" style="width:{int(s/mx_deu*100)}%"></div></div><span class="cv">{fmt(s)}</span></div>' for n,s in top) or '<p style="color:var(--muted);font-size:.84rem;padding:12px 0">Sin deudores 🎉</p>'

    # ── HTML actividad ──
    act_html="".join(f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[0]}</span><span class="log-user">{a[1]}</span><span class="log-msg"><b>{a[2]}</b> — {a[3]}{" · "+a[4] if a[4] else ""}</span></div>' for a in actividad) or '<p style="color:var(--muted);font-size:.84rem;padding:10px 0">Sin actividad</p>'

    import json
    body=f"""
    <h1 class="page-title">Panel General</h1>
    <p class="page-sub">Hola, <b>{session.get("display","")}</b> · {now_ar()}</p>

    {alertas}

    <div class="stats">
      <div class="scard"><div class="sicon">💰</div><div class="slabel">Total Facturado</div><div class="sval">{fmt(td)}</div></div>
      <div class="scard g"><div class="sicon">✅</div><div class="slabel">Total Cobrado</div><div class="sval">{fmt(th)}</div></div>
      <div class="scard r"><div class="sicon">🔴</div><div class="slabel">Deuda Pendiente</div><div class="sval">{fmt(deuda)}</div></div>
      <div class="scard o"><div class="sicon">💸</div><div class="slabel">Total Gastos</div><div class="sval">{fmt(tg)}</div></div>
      <div class="scard {"g" if rend>=0 else "r"}"><div class="sicon">📊</div><div class="slabel">Rendimiento Real</div><div class="sval">{fmt(rend)}</div></div>
      <div class="scard b"><div class="sicon">👥</div><div class="slabel">Clientes</div><div class="sval">{nc}</div></div>
    </div>

    <div class="fcard" style="margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-weight:600;color:var(--primary)">Cobrado vs Facturado</span>
        <span style="font-weight:700;color:var(--success)">{pct}%</span>
      </div>
      <div class="progwrap"><div class="progbar" style="width:{pct}%"></div></div>
    </div>

    <!-- Socias cards -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="partner-card">
        <div class="partner-name">🏦 Natasha Carlon</div>
        <div class="partner-amt" style="color:var(--primary)">{fmt(cobro_nat)}</div>
        <div style="font-size:.72rem;color:var(--muted)">{pct_nat}% del total cobrado</div>
      </div>
      <div class="partner-card">
        <div class="partner-name">🏦 Maira Carlon</div>
        <div class="partner-amt" style="color:var(--info)">{fmt(cobro_mai)}</div>
        <div style="font-size:.72rem;color:var(--muted)">{pct_mai}% del total cobrado</div>
      </div>
    </div>

    <!-- Gráfico 1: Ingresos vs Gastos -->
    <div class="fcard" style="margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
        <h3 style="border:none;padding:0;margin:0">📈 Ingresos vs Gastos — últimos meses</h3>
        <div style="display:flex;gap:14px;font-size:.76rem;color:var(--muted)">
          <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#185FA5;margin-right:4px"></span>Cobrado</span>
          <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#E24B4A;margin-right:4px"></span>Gastos</span>
        </div>
      </div>
      <div style="position:relative;height:220px"><canvas id="ch1" role="img" aria-label="Ingresos y gastos por mes"></canvas></div>
    </div>

    <!-- Fila 2: Socias + Medios de pago -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <h3 style="border:none;padding:0;margin:0">🤝 Cobros por socia</h3>
          <div style="display:flex;gap:10px;font-size:.74rem;color:var(--muted)">
            <span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#185FA5;margin-right:3px"></span>Natasha</span>
            <span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#0F6E56;margin-right:3px"></span>Maira</span>
          </div>
        </div>
        <div style="position:relative;height:185px"><canvas id="ch2" role="img" aria-label="Cobros por socia por mes"></canvas></div>
      </div>
      <div class="fcard" style="margin-bottom:0">
        <h3 style="border:none;padding:0;margin:0 0 10px">💳 Medios de pago</h3>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
          <div style="position:relative;height:160px;width:160px;flex-shrink:0"><canvas id="ch3" role="img" aria-label="Distribución de medios de pago"></canvas></div>
          <div id="leg3" style="font-size:.74rem;color:var(--muted);display:flex;flex-direction:column;gap:5px"></div>
        </div>
      </div>
    </div>

    <!-- Fila 3: Gastos cat + Rendimiento acumulado -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0">
        <h3 style="border:none;padding:0;margin:0 0 12px">💸 Gastos por categoría</h3>
        <div id="gcat" style="display:flex;flex-direction:column;gap:7px"></div>
      </div>
      <div class="fcard" style="margin-bottom:0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <h3 style="border:none;padding:0;margin:0">📊 Rendimiento acumulado</h3>
          <div style="display:flex;gap:10px;font-size:.74rem;color:var(--muted)">
            <span><span style="display:inline-block;width:20px;height:3px;background:#1D9E75;margin-right:3px;vertical-align:middle"></span>Ingresos</span>
            <span><span style="display:inline-block;width:20px;height:3px;background:#E24B4A;border-top:2px dashed #E24B4A;margin-right:3px;vertical-align:middle"></span>Gastos</span>
          </div>
        </div>
        <div style="position:relative;height:170px"><canvas id="ch4" role="img" aria-label="Rendimiento acumulado ingresos vs gastos"></canvas></div>
      </div>
    </div>

    <!-- Fila 4: Top deudores + Actividad -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0"><h3>🔴 Top Deudores</h3>{barras_deu}</div>
      <div class="fcard" style="margin-bottom:0"><h3>🕓 Actividad Reciente</h3>{act_html}</div>
    </div>

    <div class="qa">
      <a href="/clientes" class="btn btn-p">👥 Clientes</a>
      <a href="/deudas" class="btn btn-a">🔔 Deudores ({nd})</a>
      <a href="/gastos" class="btn btn-o">💸 Gastos</a>
      <a href="/caja" class="btn btn-o">🗃️ Caja</a>
      <a href="/reportes" class="btn btn-b">📊 Reportes</a>
      <a href="/usuarios" class="btn btn-o">👤 Usuarios</a>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <script>
    const P  = {json.dumps(periodos)};
    const IM = {json.dumps(ingresos_m)};
    const GM = {json.dumps(gastos_m)};
    const NM = {json.dumps(nat_m)};
    const MM = {json.dumps(mai_m)};
    const ML = {json.dumps(medios_labels)};
    const MD = {json.dumps(medios_data)};
    const GL = {json.dumps(gcat_labels)};
    const GD = {json.dumps(gcat_data)};
    const CI = {json.dumps(cum_ing)};
    const CG = {json.dumps(cum_gas)};

    const MCOLS = ['#185FA5','#0F6E56','#1D9E75','#E67E22','#7B68EE','#E24B4A','#888780'];
    const isDark = matchMedia('(prefers-color-scheme: dark)').matches;
    const gc = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
    const tc = isDark ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.42)';
    const fmtK = v => '$' + (Math.abs(v)>=1000000 ? (v/1000000).toFixed(1)+'M' : Math.abs(v)>=1000 ? (v/1000).toFixed(0)+'k' : Math.round(v));
    const fmtFull = v => '$' + Math.round(v).toLocaleString('es-AR');
    const base = {{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>' '+ctx.dataset.label+': '+fmtFull(ctx.raw)}}}}}},
      scales:{{x:{{ticks:{{color:tc,font:{{size:10}},autoSkip:false,maxRotation:0}},grid:{{color:gc}}}},
               y:{{ticks:{{color:tc,font:{{size:10}},callback:fmtK}},grid:{{color:gc}}}}}}}};

    new Chart(document.getElementById('ch1'),{{type:'bar',
      data:{{labels:P,datasets:[
        {{label:'Cobrado',data:IM,backgroundColor:'#185FA5',borderRadius:4}},
        {{label:'Gastos', data:GM,backgroundColor:'#E24B4A',borderRadius:4}}
      ]}},options:base}});

    new Chart(document.getElementById('ch2'),{{type:'bar',
      data:{{labels:P,datasets:[
        {{label:'Natasha',data:NM,backgroundColor:'#185FA5',borderRadius:3}},
        {{label:'Maira',  data:MM,backgroundColor:'#0F6E56',borderRadius:3}}
      ]}},options:base}});

    new Chart(document.getElementById('ch3'),{{type:'doughnut',
      data:{{labels:ML,datasets:[{{data:MD,backgroundColor:MCOLS.slice(0,ML.length),
        borderWidth:2,borderColor:isDark?'#1a1a1a':'#fff'}}]}},
      options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',
        plugins:{{legend:{{display:false}},
          tooltip:{{callbacks:{{label:ctx=>' '+ctx.label+': '+ctx.raw+'%'}}}}}}}}}});
    const leg3=document.getElementById('leg3');
    ML.forEach((l,i)=>{{leg3.innerHTML+=`<span style="display:flex;align-items:center;gap:5px"><span style="width:9px;height:9px;border-radius:2px;background:${{MCOLS[i]}};flex-shrink:0;display:inline-block"></span>${{l}} <b style="color:var(--text)">${{MD[i]}}%</b></span>`;}});

    const gcDiv=document.getElementById('gcat');
    const maxG=Math.max(...GD)||1;
    GL.forEach((l,i)=>{{gcDiv.innerHTML+=`<div style="display:flex;align-items:center;gap:7px;font-size:.78rem"><span style="width:100px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{l}}</span><div style="flex:1;background:var(--border);border-radius:3px;height:7px"><div style="width:${{Math.round(GD[i]/maxG*100)}}%;height:100%;background:#E67E22;border-radius:3px"></div></div><span style="width:70px;text-align:right;font-weight:600;color:var(--text)">${{fmtK(GD[i])}}</span></div>`;}});

    new Chart(document.getElementById('ch4'),{{type:'line',
      data:{{labels:P,datasets:[
        {{label:'Ingresos',data:CI,borderColor:'#1D9E75',backgroundColor:'rgba(29,158,117,0.07)',
          fill:true,tension:0.35,pointRadius:3,pointBackgroundColor:'#1D9E75'}},
        {{label:'Gastos',  data:CG,borderColor:'#E24B4A',backgroundColor:'rgba(226,75,74,0.05)',
          fill:true,tension:0.35,pointRadius:3,pointBackgroundColor:'#E24B4A',borderDash:[5,3]}}
      ]}},options:base}});
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Panel",body,"Panel")

@app.route("/clientes",methods=["GET","POST"])
@login_req
def clientes():
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        nombre=request.form.get("nombre","").strip();cuit=request.form.get("cuit","").strip()
        tel=request.form.get("telefono","").strip();email=request.form.get("email","").strip()
        abono=request.form.get("abono",0) or 0
        c.execute("INSERT INTO clientes(nombre,cuit,telefono,email,abono) VALUES(%s,%s,%s,%s,%s)",(nombre,cuit,tel,email,abono))
        conn.commit()
        periodo=datetime.now().strftime("%m/%Y")
        c.execute("SELECT id FROM clientes WHERE nombre=%s ORDER BY id DESC LIMIT 1",(nombre,))
        row=c.fetchone()
        if row:
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,%s,0)",(row[0],periodo,float(abono) if abono else 0))
            conn.commit();registrar_auditoria("NUEVO CLIENTE",f"CUIT:{cuit} Hon:{fmt(abono)}",row[0],nombre)
        flash=f'<div class="flash fok">✅ Cliente <b>{nombre}</b> agregado</div>'
    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes ORDER BY nombre")
    data=c.fetchall();conn.close();es_admin=session.get("rol")=="admin"
    rows=""
    for d in data:
        cid,nombre,cuit,tel,email,abono=d
        btn_del=f'<button onclick="confBorrar({cid},\'{nombre.replace(chr(39),"")}\',event)" class="btn btn-xs btn-r">🗑</button>' if es_admin else ""
        rows+=f'<tr data-search="{nombre.lower()} {(cuit or "").lower()} {(email or "").lower()}"><td class="nm">{nombre}</td><td class="mu">{cuit or "—"}</td><td class="mu">{tel or "—"}</td><td class="mu">{email or "—"}</td><td>{fmt(abono or 0)}</td><td style="white-space:nowrap;display:flex;gap:5px;flex-wrap:wrap"><a href="/cuenta/{cid}" class="btn btn-xs btn-p">📋 Cuenta</a><a href="/editar_cliente/{cid}" class="btn btn-xs btn-o">✏️</a>{btn_del}</td></tr>'
    modal='<div class="mo" id="mb"><div class="modal"><h3>¿Eliminar cliente?</h3><p class="msub" id="mb-nm"></p><p style="font-size:.81rem;color:var(--muted)">Se eliminan todos sus registros. No se puede deshacer.</p><div class="mact"><button class="btn btn-o" onclick="closeM(\'mb\')">Cancelar</button><a id="mb-ok" href="#" class="btn btn-r">Eliminar</a></div></div></div>' if es_admin else ""
    body=f"""
    <h1 class="page-title">Clientes</h1><p class="page-sub">{len(data)} clientes registrados</p>{flash}
    <div class="fcard"><h3>➕ Nuevo Cliente</h3><form method="post">
      <div class="fgrid">
        <div class="fg"><label>Nombre / Razón Social *</label><input name="nombre" required placeholder="García Juan"></div>
        <div class="fg"><label>CUIT</label><input name="cuit" placeholder="20-12345678-9"></div>
        <div class="fg"><label>Teléfono</label><input name="telefono" placeholder="3846000000"></div>
        <div class="fg"><label>Email</label><input name="email" type="email" placeholder="cliente@email.com"></div>
        <div class="fg"><label>Honorarios $ / mes</label><input name="abono" type="number" placeholder="0"></div>
      </div>
      <button class="btn btn-p">Guardar Cliente</button>
    </form></div>
    <div class="search"><span>🔍</span><input id="bus" placeholder="Buscar por nombre, CUIT o email..." oninput="filt(this.value)"></div>
    <div class="dtable"><table>
      <thead><tr><th>Nombre</th><th>CUIT</th><th>Teléfono</th><th>Email</th><th>Honorarios</th><th>Acciones</th></tr></thead>
      <tbody id="tb">{rows}</tbody>
    </table></div>{modal}
    <script>
    function filt(q){{q=q.toLowerCase();document.querySelectorAll('#tb tr').forEach(r=>r.style.display=r.dataset.search.includes(q)?'':'none')}}
    function confBorrar(id,nm,e){{e.preventDefault();document.getElementById('mb-nm').textContent=nm;document.getElementById('mb-ok').href='/borrar_cliente/'+id;document.getElementById('mb').classList.add('on')}}
    function closeM(id){{document.getElementById(id).classList.remove('on')}}
    document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}))
    </script>"""
    return page("Clientes",body,"Clientes")

@app.route("/editar_cliente/<int:id>",methods=["GET","POST"])
@login_req
def editar_cliente(id):
    conn=conectar();c=conn.cursor()
    if request.method=="POST":
        c.execute("SELECT nombre,cuit,telefono,email,abono FROM clientes WHERE id=%s",(id,))
        antes=c.fetchone()
        nombre=request.form.get("nombre","").strip();cuit=request.form.get("cuit","").strip()
        tel=request.form.get("telefono","").strip();email=request.form.get("email","").strip();abono=request.form.get("abono",0) or 0
        c.execute("UPDATE clientes SET nombre=%s,cuit=%s,telefono=%s,email=%s,abono=%s WHERE id=%s",(nombre,cuit,tel,email,abono,id))
        conn.commit()
        cambios=[f"{campo}: '{ant}' → '{nvo}'" for campo,ant,nvo in zip(["Nombre","CUIT","Teléfono","Email","Honorarios"],antes,[nombre,cuit,tel,email,str(abono)]) if str(ant or "")!=str(nvo or "")]
        if cambios: registrar_auditoria("EDICIÓN CLIENTE"," | ".join(cambios),id,nombre)
        conn.close();return redirect("/clientes")
    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes WHERE id=%s",(id,))
    d=c.fetchone();conn.close()
    body=f'<a href="/clientes" class="btn btn-o btn-sm" style="margin-bottom:18px">← Volver</a><h1 class="page-title">Editar Cliente</h1><p class="page-sub">{d[1]}</p><div class="fcard"><form method="post"><div class="fgrid"><div class="fg"><label>Nombre</label><input name="nombre" value="{d[1] or ""}" required></div><div class="fg"><label>CUIT</label><input name="cuit" value="{d[2] or ""}"></div><div class="fg"><label>Teléfono</label><input name="telefono" value="{d[3] or ""}"></div><div class="fg"><label>Email</label><input name="email" type="email" value="{d[4] or ""}"></div><div class="fg"><label>Honorarios $</label><input name="abono" type="number" value="{d[5] or 0}"></div></div><div style="display:flex;gap:8px"><button class="btn btn-p">Guardar</button><a href="/clientes" class="btn btn-o">Cancelar</a></div></form></div>'
    return page(f"Editar — {d[1]}",body,"Clientes")

@app.route("/borrar_cliente/<int:id>")
@admin_req
def borrar_cliente(id):
    conn=conectar();c=conn.cursor()
    c.execute("SELECT nombre FROM clientes WHERE id=%s",(id,));row=c.fetchone();nombre=row[0] if row else "?"
    c.execute("DELETE FROM cuentas WHERE cliente_id=%s",(id,));c.execute("DELETE FROM pagos WHERE cliente_id=%s",(id,));c.execute("DELETE FROM clientes WHERE id=%s",(id,))
    conn.commit();conn.close();registrar_auditoria("BAJA CLIENTE","Cliente eliminado",id,nombre);return redirect("/clientes")

@app.route("/cuenta/<int:id>",methods=["GET","POST"])
@login_req
def cuenta(id):
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        periodo=request.form.get("periodo","").strip();pago=float(request.form.get("pago",0) or 0)
        medio=request.form.get("medio","Efectivo");obs=request.form.get("observaciones","").strip()
        facturado=request.form.get("facturado","0")=="1"
        c.execute("SELECT id,haber FROM cuentas WHERE cliente_id=%s AND periodo=%s",(id,periodo))
        row=c.fetchone();haber_ant=row[1] or 0 if row else 0
        if row: c.execute("UPDATE cuentas SET haber=COALESCE(haber,0)+%s WHERE cliente_id=%s AND periodo=%s",(pago,id,periodo))
        else: c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,0,%s)",(id,periodo,pago))
        conn.commit()
        c.execute("SELECT nombre FROM clientes WHERE id=%s",(id,));nom=c.fetchone();nombre_cli=nom[0] if nom else "?"
        c.execute("INSERT INTO pagos(cliente_id,periodo,monto,medio,observaciones,facturado,fecha,usuario,emitido_por) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(id,periodo,pago,medio,obs,facturado,now_ar(),session.get("display",""),session.get("display","")))
        conn.commit()
        registrar_auditoria("PAGO REGISTRADO",f"Periodo:{periodo} | Monto:{fmt(pago)} | Medio:{medio} | Facturado:{'Sí' if facturado else 'No'} | Ant:{fmt(haber_ant)}",id,nombre_cli)
        flash=f'<div class="flash fok">✅ Pago de {fmt(pago)} registrado — {medio}</div>'
    c.execute("SELECT nombre,cuit,telefono,email FROM clientes WHERE id=%s",(id,))
    cli=c.fetchone()
    if not cli: return "Cliente no encontrado",404
    nombre,cuit,tel,email=cli
    c.execute("SELECT periodo,debe,haber FROM cuentas WHERE cliente_id=%s ORDER BY SUBSTRING(periodo,4,4) DESC,SUBSTRING(periodo,1,2) DESC",(id,))
    datos=c.fetchall()
    c.execute("SELECT fecha,usuario,periodo,monto,medio,facturado,observaciones,emitido_por FROM pagos WHERE cliente_id=%s ORDER BY id DESC LIMIT 30",(id,))
    historial=c.fetchall()
    conn.close()
    total_deuda=sum(max(d[1]-d[2],0) for d in datos);total_pago=sum(d[2] for d in datos)
    filas=""
    for d in datos:
        saldo=d[1]-d[2]
        if saldo<=0: badge='<span class="badge bp">✓ PAGADO</span>'
        elif d[2]>0: badge=f'<span class="badge bpar">PARCIAL · debe {fmt(saldo)}</span>'
        else: badge=f'<span class="badge bd">DEBE {fmt(saldo)}</span>'
        telefono=(tel or "").replace(" ","").replace("+","").strip()
        wa_msg=f"Hola {nombre}, tiene deuda de {fmt(saldo)} del periodo {d[0]}. Transferir al CBU 0110420630042013452529 Alias: ESTUDIO.CONTA.CARLON"
        wa_link=f"https://wa.me/{telefono}?text={wa_msg.replace(' ','%20')}" if telefono else "#"
        pu=d[0].replace("/","-")
        btn_p=f'<button onclick="abrirPago(\'{d[0]}\',{saldo})" class="btn btn-xs btn-g">💳 Pagar</button>' if saldo>0 else '<span style="color:var(--success);font-size:.73rem;font-weight:600">✓ Al día</span>'
        filas+=f'<div class="arow"><span class="period">{d[0]}</span><span style="font-size:.86rem">{fmt(d[2] if d[2]>0 else d[1])}</span>{badge}<div style="display:flex;gap:5px;flex-wrap:wrap"><a href="/recibo/{id}/{pu}" target="_blank" class="btn btn-xs btn-o">📄 Ver</a><a href="/recibo/{id}/{pu}?download=1" class="btn btn-xs btn-o">⬇ PDF</a>{btn_p}<a href="https://afip.gob.ar/facturacion/" target="_blank" class="btn btn-xs btn-arca">🧾 ARCA</a>{"<a href="+chr(39)+wa_link+chr(39)+" target=_blank class=btn btn-xs btn-wa>📱 WA</a>" if telefono else ""}</div></div>'
    hist_rows=""
    for h in historial:
        fact_b='<span style="color:var(--success);font-size:.69rem;font-weight:700">● Facturado</span>' if h[5] else '<span style="color:var(--muted);font-size:.69rem">○ Sin factura</span>'
        emitido=h[7] or h[1]
        hist_rows+=f'<div class="logrow"><div class="log-dot" style="background:var(--success)"></div><span class="log-time">{h[0]}</span><span class="log-user">{emitido}</span><span class="log-msg">Periodo <b>{h[2]}</b> · {fmt(h[3])} · <span class="bmedio">{h[4]}</span> · {fact_b}{" · <i style=color:var(--muted)>"+h[6]+"</i>" if h[6] else ""}</span></div>'
    medios_opts="".join(f'<option value="{m}">{m}</option>' for m in MEDIOS_PAGO)
    body=f"""
    <a href="/clientes" class="btn btn-o btn-sm" style="margin-bottom:18px">← Clientes</a>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px">
      <div><h1 class="page-title">{nombre}</h1><p class="page-sub">CUIT: {cuit or "—"} · Tel: {tel or "—"} · {email or "—"}</p></div>
      <div style="text-align:right">
        <div style="font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px">Deuda Total</div>
        <div style="font-family:'DM Serif Display',serif;font-size:1.85rem;color:{"var(--danger)" if total_deuda>0 else "var(--success)"}">
          {fmt(total_deuda)}</div>
        <div style="font-size:.73rem;color:var(--muted)">Total cobrado: {fmt(total_pago)}</div>
      </div>
    </div>
    {flash}
    <div>{filas or '<p style="color:var(--muted);padding:28px;text-align:center">Sin movimientos</p>'}</div>
    <div class="fcard" style="margin-top:20px"><h3>📋 Historial de Pagos</h3>
      {hist_rows or '<p style="color:var(--muted);font-size:.84rem">Sin pagos registrados</p>'}
    </div>
    <div class="mo" id="mp"><div class="modal">
      <h3>💳 Registrar Pago</h3><p class="msub" id="mp-sub"></p>
      <form method="post">
        <input type="hidden" name="periodo" id="mp-per">
        <div class="fgrid" style="grid-template-columns:1fr 1fr">
          <div class="fg"><label>Monto $</label><input name="pago" id="mp-monto" type="number" step="0.01" required style="font-size:1.05rem;font-weight:600"></div>
          <div class="fg"><label>Medio de Pago</label><select name="medio">{medios_opts}</select></div>
        </div>
        <div class="fg" style="margin-bottom:12px"><label>Observaciones</label><input name="observaciones" placeholder="Ej: cheque N°12345, pago parcial..."></div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding:10px;background:#f0f9f4;border-radius:8px">
          <input type="checkbox" name="facturado" value="1" id="chk-fact" style="width:16px;height:16px">
          <label for="chk-fact" style="font-size:.84rem;font-weight:600;color:var(--primary);cursor:pointer">🧾 Se emitió factura en ARCA para este pago</label>
        </div>
        <div style="background:#f0f4ff;border-radius:8px;padding:9px 12px;margin-bottom:12px;font-size:.77rem;color:#1a3a8a">
          💡 Para facturar, clic en <a href="https://afip.gob.ar/facturacion/" target="_blank" class="btn btn-xs btn-arca" style="display:inline-flex">🧾 ARCA</a> en la fila correspondiente, luego volvé y marcá la casilla.
        </div>
        <div class="mact">
          <button type="button" class="btn btn-o" onclick="closeM('mp')">Cancelar</button>
          <button type="submit" class="btn btn-g">Confirmar Pago ✓</button>
        </div>
      </form>
    </div></div>
    <script>
    function abrirPago(p,s){{document.getElementById('mp-sub').textContent='Periodo: '+p+' — Saldo: $'+Number(s).toLocaleString('es-AR');document.getElementById('mp-per').value=p;document.getElementById('mp-monto').value=s;document.getElementById('mp').classList.add('on')}}
    function closeM(id){{document.getElementById(id).classList.remove('on')}}
    document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}))
    </script>"""
    return page(nombre,body,"Clientes")

@app.route("/deudas")
@login_req
def deudas():
    conn=conectar();c=conn.cursor()
    c.execute("SELECT cl.id,cl.nombre,cl.telefono,SUM(cu.debe-cu.haber) d FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id GROUP BY cl.id,cl.nombre,cl.telefono HAVING SUM(cu.debe-cu.haber)>0 ORDER BY d DESC")
    data=c.fetchall();conn.close();total=sum(d[3] for d in data)
    cards=""
    for d in data:
        tel=(d[2] or "").replace(" ","").replace("+","")
        wa=f'<a href="https://wa.me/{tel}?text=Hola%20{d[1].replace(" ","%20")}%2C%20tiene%20saldo%20de%20{fmt(d[3])}%20con%20Estudio%20Carlon.%20CBU%3A0110420630042013452529" target="_blank" class="btn btn-xs btn-wa">📱 WA</a>' if tel else ""
        cards+=f'<div class="dcard"><div><div class="dname">{d[1]}</div><div style="font-size:.76rem;color:var(--muted)">Tel: {d[2] or "—"}</div></div><div style="display:flex;align-items:center;gap:8px"><span class="damt">{fmt(d[3])}</span><a href="/cuenta/{d[0]}" class="btn btn-xs btn-p">📋 Cuenta</a>{wa}</div></div>'
    body=f'<h1 class="page-title">Deudores</h1><p class="page-sub">{len(data)} clientes · Total: <b>{fmt(total)}</b></p>{cards or "<p style=color:var(--muted);text-align:center;padding:48px;font-size:1.1rem>🎉 Sin deudores</p>"}'
    return page("Deudores",body,"Deudores")

@app.route("/gastos",methods=["GET","POST"])
@login_req
def gastos():
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        accion=request.form.get("accion","crear")
        if accion=="crear":
            fecha=request.form.get("fecha",datetime.now().strftime("%d/%m/%Y"))
            cat=request.form.get("categoria","Otros");desc=request.form.get("descripcion","").strip()
            monto=float(request.form.get("monto",0) or 0)
            c.execute("INSERT INTO gastos(fecha,categoria,descripcion,monto,usuario) VALUES(%s,%s,%s,%s,%s)",(fecha,cat,desc,monto,session.get("display","")))
            conn.commit();registrar_auditoria("GASTO REGISTRADO",f"{cat} — {desc} — {fmt(monto)}")
            flash=f'<div class="flash fok">✅ Gasto de {fmt(monto)} en {cat} registrado</div>'
        elif accion=="borrar" and session.get("rol")=="admin":
            c.execute("DELETE FROM gastos WHERE id=%s",(request.form.get("gid"),))
            conn.commit();flash='<div class="flash fok">✅ Gasto eliminado</div>'
    mes_actual=datetime.now().strftime("%m/%Y")
    c.execute("SELECT categoria,SUM(monto) FROM gastos WHERE fecha LIKE %s GROUP BY categoria ORDER BY SUM(monto) DESC",(f"%{mes_actual}%",))
    resumen=c.fetchall()
    c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos");total_g=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE fecha LIKE %s",(f"%{mes_actual}%",));mes_g=c.fetchone()[0]
    c.execute("SELECT id,fecha,categoria,descripcion,monto,usuario FROM gastos ORDER BY id DESC LIMIT 50")
    lista=c.fetchall();conn.close()
    cat_opts="".join(f'<option value="{cat}">{cat}</option>' for cat in CATEGORIAS_GASTO)
    res_html=""
    mx_g=resumen[0][1] if resumen else 1
    for cat,monto in resumen:
        res_html+=f'<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:.82rem;margin-bottom:4px"><span style="font-weight:600">{cat}</span><span style="color:var(--danger)">{fmt(monto)}</span></div><div class="progwrap"><div style="height:100%;width:{int(monto/mx_g*100)}%;background:var(--warning);border-radius:6px"></div></div></div>'
    es_admin=session.get("rol")=="admin"
    rows=""
    for g in lista:
        btn_del=f'<form method="post" style="display:inline"><input type="hidden" name="accion" value="borrar"><input type="hidden" name="gid" value="{g[0]}"><button class="btn btn-xs btn-r" onclick="return confirm(\'¿Eliminar?\')">🗑</button></form>' if es_admin else ""
        rows+=f'<tr><td class="mu">{g[1]}</td><td><span class="bmedio">{g[2]}</span></td><td>{g[3] or "—"}</td><td style="font-weight:600;color:var(--danger)">{fmt(g[4])}</td><td class="mu">{g[5]}</td><td>{btn_del}</td></tr>'
    body=f"""
    <h1 class="page-title">Gastos del Estudio</h1>
    <p class="page-sub">Control de egresos para calcular el rendimiento real</p>{flash}
    <div class="stats">
      <div class="scard o"><div class="sicon">💸</div><div class="slabel">Total Gastos</div><div class="sval">{fmt(total_g)}</div></div>
      <div class="scard r"><div class="sicon">📅</div><div class="slabel">Gastos {mes_actual}</div><div class="sval">{fmt(mes_g)}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px" class="twocol">
      <div class="fcard" style="margin-bottom:0"><h3>➕ Registrar Gasto</h3>
        <form method="post"><input type="hidden" name="accion" value="crear">
          <div class="fgrid">
            <div class="fg"><label>Categoría</label><select name="categoria">{cat_opts}</select></div>
            <div class="fg"><label>Monto $</label><input name="monto" type="number" step="0.01" required placeholder="0"></div>
            <div class="fg"><label>Descripción</label><input name="descripcion" placeholder="Detalle opcional"></div>
            <div class="fg"><label>Fecha</label><input name="fecha" value="{datetime.now().strftime('%d/%m/%Y')}" placeholder="dd/mm/yyyy"></div>
          </div>
          <button class="btn btn-p">Registrar Gasto</button>
        </form>
      </div>
      <div class="fcard" style="margin-bottom:0"><h3>📊 Resumen {mes_actual}</h3>
        {res_html or '<p style="color:var(--muted);font-size:.84rem">Sin gastos este mes</p>'}
      </div>
    </div>
    <div class="dtable"><table>
      <thead><tr><th>Fecha</th><th>Categoría</th><th>Descripción</th><th>Monto</th><th>Cargado por</th><th></th></tr></thead>
      <tbody>{rows or '<tr><td colspan=6 style="color:var(--muted);text-align:center;padding:20px">Sin gastos registrados</td></tr>'}</tbody>
    </table></div>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Gastos",body,"Gastos")

@app.route("/reportes")
@admin_req
def reportes():
    conn=conectar();c=conn.cursor()
    c.execute("SELECT periodo,SUM(debe),SUM(haber),SUM(debe-haber) FROM cuentas GROUP BY periodo ORDER BY SUBSTRING(periodo,4,4) DESC,SUBSTRING(periodo,1,2) DESC")
    por_mes=c.fetchall()
    c.execute("SELECT cl.nombre,SUM(cu.debe),SUM(cu.haber),SUM(cu.debe-cu.haber) FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id GROUP BY cl.nombre ORDER BY SUM(cu.debe-cu.haber) DESC LIMIT 20")
    ranking=c.fetchall()
    c.execute("SELECT medio,SUM(monto),COUNT(*) FROM pagos GROUP BY medio ORDER BY SUM(monto) DESC")
    por_medio=c.fetchall()
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Natasha%'");nat=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Maira%'");mai=c.fetchone()[0]
    c.execute("SELECT categoria,SUM(monto) FROM gastos GROUP BY categoria ORDER BY SUM(monto) DESC")
    gastos_cat=c.fetchall()
    c.execute("SELECT fecha,usuario,accion,detalle,cliente_nombre FROM auditoria ORDER BY id DESC LIMIT 100")
    auditoria=c.fetchall()
    c.execute("SELECT nombre FROM clientes WHERE abono IS NULL OR abono=0 ORDER BY nombre")
    sin_abono=c.fetchall()
    conn.close()
    filas_mes="".join(f'<tr><td class="nm">{r[0]}</td><td>{fmt(r[1])}</td><td style="color:var(--success);font-weight:600">{fmt(r[2])}</td><td style="color:{"var(--danger)" if (r[3] or 0)>0 else "var(--success)"};font-weight:600">{fmt(r[3] or 0)}</td></tr>' for r in por_mes)
    filas_rank="".join(f'<tr><td class="nm">{r[0]}</td><td>{fmt(r[1])}</td><td style="color:var(--success)">{fmt(r[2])}</td><td style="color:{"var(--danger)" if (r[3] or 0)>0 else "var(--success)"}"><b>{fmt(r[3] or 0)}</b></td></tr>' for r in ranking)
    filas_medio="".join(f'<tr><td class="nm"><span class="bmedio">{r[0]}</span></td><td style="font-weight:600;color:var(--success)">{fmt(r[1])}</td><td class="mu">{r[2]} pagos</td></tr>' for r in por_medio)
    filas_gastos="".join(f'<tr><td class="nm">{r[0]}</td><td style="color:var(--danger);font-weight:600">{fmt(r[1])}</td></tr>' for r in gastos_cat)
    filas_aud="".join(f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[0]}</span><span class="log-user">{a[1]}</span><span class="log-msg"><b>{a[2]}</b>{" · "+a[4] if a[4] else ""} — {a[3]}</span></div>' for a in auditoria)
    sin_ab=f'<div class="warn-box">⚠️ <b>{len(sin_abono)}</b> clientes sin honorarios: {", ".join(s[0] for s in sin_abono[:12])}{"..." if len(sin_abono)>12 else ""}</div>' if sin_abono else ""
    total_s=nat+mai;pct_nat=int(nat/total_s*100) if total_s>0 else 50;pct_mai=100-pct_nat
    body=f"""
    <h1 class="page-title">Reportes</h1><p class="page-sub">Resúmenes financieros y auditoría</p>{sin_ab}
    <div class="fcard"><h3>🤝 Distribución entre Socias</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:12px" class="twocol">
        <div style="text-align:center;padding:14px;background:#f0f9f4;border-radius:10px">
          <div style="font-weight:600;color:var(--primary);margin-bottom:6px">🏦 Natasha Carlon</div>
          <div style="font-family:'DM Serif Display',serif;font-size:1.8rem;color:var(--primary)">{fmt(nat)}</div>
          <div style="font-size:.74rem;color:var(--muted)">{pct_nat}% del total</div>
        </div>
        <div style="text-align:center;padding:14px;background:#f0f4ff;border-radius:10px">
          <div style="font-weight:600;color:var(--info);margin-bottom:6px">🏦 Maira Carlon</div>
          <div style="font-family:'DM Serif Display',serif;font-size:1.8rem;color:var(--info)">{fmt(mai)}</div>
          <div style="font-size:.74rem;color:var(--muted)">{pct_mai}% del total</div>
        </div>
      </div>
      <div style="display:flex;height:14px;border-radius:7px;overflow:hidden">
        <div style="width:{pct_nat}%;background:var(--primary)"></div>
        <div style="width:{pct_mai}%;background:var(--info)"></div>
      </div>
    </div>
    <div class="tabs">
      <button class="tab on" onclick="showTab('t1',this)">📅 Por Período</button>
      <button class="tab" onclick="showTab('t2',this)">🏆 Clientes</button>
      <button class="tab" onclick="showTab('t3',this)">💳 Medios de Pago</button>
      <button class="tab" onclick="showTab('t4',this)">💸 Gastos</button>
      <button class="tab" onclick="showTab('t5',this)">🔍 Auditoría</button>
    </div>
    <div id="t1" class="tabpanel on"><div class="dtable"><table><thead><tr><th>Período</th><th>Facturado</th><th>Cobrado</th><th>Deuda</th></tr></thead><tbody>{filas_mes or "<tr><td colspan=4 style=color:var(--muted);text-align:center;padding:20px>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t2" class="tabpanel"><div class="dtable"><table><thead><tr><th>Cliente</th><th>Facturado</th><th>Cobrado</th><th>Saldo</th></tr></thead><tbody>{filas_rank or "<tr><td colspan=4 style=color:var(--muted);text-align:center;padding:20px>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t3" class="tabpanel"><div class="dtable"><table><thead><tr><th>Medio de Pago</th><th>Total Cobrado</th><th>Cantidad</th></tr></thead><tbody>{filas_medio or "<tr><td colspan=3 style=color:var(--muted);text-align:center;padding:20px>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t4" class="tabpanel"><div class="dtable"><table><thead><tr><th>Categoría</th><th>Total</th></tr></thead><tbody>{filas_gastos or "<tr><td colspan=2 style=color:var(--muted);text-align:center;padding:20px>Sin gastos</td></tr>"}</tbody></table></div></div>
    <div id="t5" class="tabpanel"><div class="fcard"><h3>🔍 Registro de acciones</h3>{filas_aud or "<p style=color:var(--muted);font-size:.84rem>Sin actividad</p>"}</div></div>
    <script>function showTab(id,btn){{document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));document.getElementById(id).classList.add('on');btn.classList.add('on')}}</script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Reportes",body,"Reportes")

@app.route("/usuarios",methods=["GET","POST"])
@admin_req
def usuarios():
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        accion=request.form.get("accion","crear")
        if accion=="crear":
            usuario=request.form.get("usuario","").strip();clave=request.form.get("clave","").strip()
            rol=request.form.get("rol","secretaria");display=request.form.get("nombre_display","").strip() or usuario
            if not usuario or not clave: flash='<div class="flash ferr">❌ Completá usuario y contraseña</div>'
            else:
                c.execute("SELECT id FROM usuarios WHERE usuario=%s",(usuario,))
                if c.fetchone(): flash='<div class="flash ferr">❌ Ese usuario ya existe</div>'
                else:
                    c.execute("INSERT INTO usuarios(usuario,clave,rol,nombre_display) VALUES(%s,%s,%s,%s)",(usuario,generate_password_hash(clave),rol,display))
                    conn.commit();registrar_auditoria("NUEVO USUARIO",f"@{usuario} Rol:{rol}")
                    flash=f'<div class="flash fok">✅ Usuario <b>{display}</b> creado</div>'
        elif accion=="cambiar_clave":
            uid=request.form.get("uid");nueva=request.form.get("nueva_clave","").strip()
            if nueva and len(nueva)>=4:
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s",(generate_password_hash(nueva),uid))
                conn.commit();c.execute("SELECT usuario FROM usuarios WHERE id=%s",(uid,));u=c.fetchone()
                registrar_auditoria("CAMBIO CLAVE",f"@{u[0] if u else uid}")
                flash='<div class="flash fok">✅ Contraseña actualizada</div>'
            else: flash='<div class="flash ferr">❌ Mínimo 4 caracteres</div>'
        elif accion=="cambiar_mis_datos":
            nd2=request.form.get("nuevo_display","").strip();nu=request.form.get("nuevo_usuario","").strip();nc2=request.form.get("nueva_clave_admin","").strip()
            user_actual=session.get("user")
            if nd2: c.execute("UPDATE usuarios SET nombre_display=%s WHERE usuario=%s",(nd2,user_actual));session["display"]=nd2
            if nu and nu!=user_actual:
                c.execute("SELECT id FROM usuarios WHERE usuario=%s",(nu,))
                if not c.fetchone(): c.execute("UPDATE usuarios SET usuario=%s WHERE usuario=%s",(nu,user_actual));session["user"]=nu
            if nc2 and len(nc2)>=4: c.execute("UPDATE usuarios SET clave=%s WHERE usuario=%s",(generate_password_hash(nc2),session.get("user")))
            conn.commit();registrar_auditoria("EDICIÓN PERFIL","Admin actualizó sus datos")
            flash='<div class="flash fok">✅ Tus datos fueron actualizados</div>'
        elif accion=="borrar_usuario":
            uid=request.form.get("uid");c.execute("SELECT usuario,nombre_display FROM usuarios WHERE id=%s",(uid,));u=c.fetchone()
            if u and u[0]!=session.get("user"):
                c.execute("DELETE FROM usuarios WHERE id=%s",(uid,));conn.commit()
                registrar_auditoria("BAJA USUARIO",f"@{u[0]}");flash='<div class="flash fok">✅ Usuario eliminado</div>'
            else: flash='<div class="flash ferr">❌ No podés eliminar tu propio usuario</div>'
    c.execute("SELECT id,usuario,rol,nombre_display FROM usuarios ORDER BY rol,usuario")
    lista=c.fetchall();conn.close()
    cards=""
    for u in lista:
        uid,uname,urol,udisp=u
        badge='<span class="badge badm">Admin</span>' if urol=="admin" else '<span class="badge bsec">Secretaria</span>'
        es_yo=uname==session.get("user")
        btn_del='<span style="font-size:.73rem;color:var(--muted)">← sos vos</span>' if es_yo else f'<form method="post" style="display:inline" onsubmit="return confirm(\'¿Eliminar a {udisp or uname}?\')"><input type=hidden name=accion value=borrar_usuario><input type=hidden name=uid value={uid}><button class="btn btn-xs btn-r">🗑</button></form>'
        cards+=f'<div class="ucard {"adm" if urol=="admin" else ""}"><div><div style="font-weight:600;font-size:.96rem;color:var(--primary)">{udisp or uname} {badge}</div><div style="font-size:.75rem;color:var(--muted)">@{uname}</div></div><div style="display:flex;gap:7px;flex-wrap:wrap"><button onclick="abrirClave({uid},\'{uname}\')" class="btn btn-xs btn-o">🔑 Cambiar clave</button>{btn_del}</div></div>'
    body=f"""
    <h1 class="page-title">Gestión de Usuarios</h1><p class="page-sub">Usuarios, contraseñas y permisos</p>{flash}
    <div class="fcard" style="border-left:4px solid var(--accent)"><h3>👤 Mis Datos — {session.get("display","")}</h3>
      <form method="post"><input type="hidden" name="accion" value="cambiar_mis_datos">
        <div class="fgrid">
          <div class="fg"><label>Nombre para mostrar</label><input name="nuevo_display" value="{session.get('display','')}"></div>
          <div class="fg"><label>Usuario (login)</label><input name="nuevo_usuario" value="{session.get('user','')}"></div>
          <div class="fg"><label>Nueva contraseña (vacío = no cambia)</label><input name="nueva_clave_admin" type="password" placeholder="Nueva contraseña"></div>
        </div>
        <button class="btn btn-a btn-sm">Guardar mis datos</button>
      </form>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px" class="twocol">
      <div class="fcard" style="margin-bottom:0"><h3>➕ Nuevo Usuario</h3>
        <form method="post"><input type="hidden" name="accion" value="crear">
          <div class="fgrid" style="grid-template-columns:1fr">
            <div class="fg"><label>Nombre completo</label><input name="nombre_display" placeholder="María González"></div>
            <div class="fg"><label>Usuario</label><input name="usuario" placeholder="mariag" required></div>
            <div class="fg"><label>Contraseña</label><input name="clave" type="password" placeholder="Mínimo 4 caracteres" required></div>
            <div class="fg"><label>Rol</label><select name="rol"><option value="secretaria">🗂 Secretaria</option><option value="admin">👑 Administrador</option></select></div>
          </div>
          <button class="btn btn-p btn-sm">Crear Usuario</button>
        </form>
      </div>
      <div class="fcard" style="margin-bottom:0"><h3>ℹ️ Permisos</h3>
        <div class="info-box" style="margin-bottom:10px"><b>👑 Admin:</b> Panel financiero · Gráficos · Control socias · Clientes (todo) · Pagos · Recibos · Reportes · Gastos · Usuarios</div>
        <div style="background:#f0f4ff;border:1px solid #b0c4ee;border-radius:8px;padding:10px 14px;font-size:.8rem;color:#1a3a8a"><b>🗂 Secretaria:</b> Agregar/editar clientes · Registrar pagos (medio+factura) · Recibos PDF · Gastos · WhatsApp · Deudores<br><b>No puede:</b> Panel financiero · borrar clientes · reportes · usuarios</div>
      </div>
    </div>
    <div class="fcard"><h3>👥 Usuarios ({len(lista)})</h3>{cards or '<p style="color:var(--muted);font-size:.84rem">Sin usuarios</p>'}</div>
    <div class="mo" id="mc"><div class="modal"><h3>🔑 Cambiar Contraseña</h3><p class="msub" id="mc-sub"></p>
      <form method="post"><input type="hidden" name="accion" value="cambiar_clave"><input type="hidden" name="uid" id="mc-uid">
        <div class="fg" style="margin-bottom:14px"><label>Nueva contraseña</label><input name="nueva_clave" type="password" placeholder="Mínimo 4 caracteres" required></div>
        <div class="mact"><button type="button" class="btn btn-o" onclick="closeM('mc')">Cancelar</button><button type="submit" class="btn btn-p">Guardar</button></div>
      </form>
    </div></div>
    <script>
    function abrirClave(id,u){{document.getElementById('mc-sub').textContent='@'+u;document.getElementById('mc-uid').value=id;document.getElementById('mc').classList.add('on')}}
    function closeM(id){{document.getElementById(id).classList.remove('on')}}
    document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}))
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Usuarios",body,"Usuarios")

def generar_pdf(cliente_id,periodo,monto):
    buffer=BytesIO();cv=canvas.Canvas(buffer,pagesize=A4);w,h=A4
    conn=conectar();c=conn.cursor()
    c.execute("SELECT nombre,cuit FROM clientes WHERE id=%s",(cliente_id,))
    data=c.fetchone();conn.close()
    cli_nombre=data[0] if data else "—";cuit_cli=data[1] if data else ""
    cv.setFillColorRGB(0.10,0.23,0.16);cv.rect(0,h-130,w,130,fill=1,stroke=0)
    for lp in ["logo.png","static/logo.png"]:
        if os.path.exists(lp):
            try: cv.drawImage(ImageReader(lp),36,h-115,width=90,height=50,preserveAspectRatio=True,mask="auto")
            except: pass
            break
    cv.setFillColorRGB(0.78,0.66,0.43);cv.setFont("Helvetica-Bold",20);cv.drawString(148,h-58,"RECIBO DE PAGO")
    cv.setFillColorRGB(1,1,1);cv.setFont("Helvetica",8.5);cv.drawString(148,h-76,"Estudio Contable Carlon — Servicios Contables e Impositivos")
    numero=datetime.now().strftime("%Y%m%d%H%M%S")
    cv.setFont("Helvetica-Bold",9);cv.drawRightString(w-36,h-50,f"N° {numero}")
    cv.setFont("Helvetica",8);cv.drawRightString(w-36,h-66,datetime.now().strftime("%d/%m/%Y %H:%M"))
    cv.setFillColorRGB(0.15,0.15,0.15);cv.setFont("Helvetica-Bold",8.5);cv.drawString(36,h-153,"EMISOR")
    cv.setFont("Helvetica",8.5);cv.drawString(36,h-168,"Estudio Contable Carlon  ·  CUIT: 27-35045505-7")
    cv.drawString(36,h-181,"Absalón Rojas s/n  ·  Quimilí, Santiago del Estero  ·  CP 3740")
    cv.setStrokeColorRGB(0.87,0.87,0.87);cv.line(36,h-195,w-36,h-195)
    cv.setFillColorRGB(0.53,0.53,0.53);cv.setFont("Helvetica-Bold",8);cv.drawString(36,h-215,"CLIENTE")
    cv.setFillColorRGB(0.10,0.23,0.16);cv.setFont("Helvetica-Bold",13);cv.drawString(36,h-232,cli_nombre)
    cv.setFont("Helvetica",8.5);cv.setFillColorRGB(0.3,0.3,0.3);cv.drawString(36,h-248,f"CUIT: {cuit_cli or '—'}   ·   Periodo: {periodo}")
    cv.setFillColorRGB(0.97,0.96,0.93);cv.roundRect(36,h-315,w-72,55,8,fill=1,stroke=0)
    cv.setFillColorRGB(0.10,0.23,0.16);cv.setFont("Helvetica-Bold",10);cv.drawString(54,h-277,"TOTAL ABONADO")
    cv.setFont("Helvetica-Bold",22)
    try: mf=f"$ {float(monto):,.0f}".replace(",",".")
    except: mf=f"$ {monto}"
    cv.drawRightString(w-54,h-277,mf)
    cv.setFont("Helvetica",8);cv.setFillColorRGB(0.45,0.45,0.45);cv.drawString(36,h-334,"Recibí conforme el importe indicado en concepto de honorarios profesionales.")
    cv.setStrokeColorRGB(0.72,0.72,0.72);cv.line(36,h-390,195,h-390);cv.line(w-195,h-390,w-36,h-390)
    cv.setFont("Helvetica",8);cv.setFillColorRGB(0.5,0.5,0.5);cv.drawString(36,h-403,"Firma");cv.drawString(w-195,h-403,"Aclaración")
    cv.setFillColorRGB(0.97,0.96,0.93);cv.roundRect(36,36,(w-72)*0.6,115,8,fill=1,stroke=0)
    cv.setFillColorRGB(0.10,0.23,0.16);cv.setFont("Helvetica-Bold",8.5);cv.drawString(52,140,"DATOS PARA TRANSFERENCIA")
    cv.setFont("Helvetica",8);cv.setFillColorRGB(0.2,0.2,0.2)
    for i,ln in enumerate(["Titular: Alexis Natasha Carlon","CUIL: 27-35045505-7  ·  Banco: Nación","Cuenta: CA $ 28324201345252","CBU: 0110420630042013452529","Alias: ESTUDIO.CONTA.CARLON"]):
        cv.drawString(52,124-i*14,ln)
    qr=qrcode.make(f"CBU:0110420630042013452529\nAlias:ESTUDIO.CONTA.CARLON\nMonto:{monto}\nCliente:{cli_nombre}\nPeriodo:{periodo}")
    qb=BytesIO();qr.save(qb);qb.seek(0)
    cv.drawImage(ImageReader(qb),w-148,34,width=106,height=106)
    cv.setFont("Helvetica-Bold",7.5);cv.setFillColorRGB(0.10,0.23,0.16);cv.drawCentredString(w-95,28,"Escaneá para pagar")
    cv.save();buffer.seek(0);return buffer

@app.route("/recibo/<int:cliente_id>/<path:periodo>")
@login_req
def ver_recibo(cliente_id,periodo):
    periodo=periodo.replace("-","/")
    conn=conectar();c=conn.cursor()
    c.execute("SELECT debe,haber FROM cuentas WHERE cliente_id=%s AND periodo=%s",(cliente_id,periodo))
    data=c.fetchone();conn.close()
    if not data: return "No hay datos para ese período",404
    monto=data[1] if data[1]>0 else data[0]
    pdf=generar_pdf(cliente_id,periodo,monto);dl=request.args.get("download")
    return send_file(pdf,mimetype="application/pdf",as_attachment=bool(dl),download_name=f"recibo_{periodo.replace('/','_')}.pdf")

@app.route("/importar",methods=["GET","POST"])
@admin_req
def importar():
    try: import pandas as pd
    except: return "pandas no instalado",500
    if request.method=="POST":
        archivo=request.files["archivo"];df=pd.read_excel(archivo)
        conn=conectar();c=conn.cursor();ok=0
        for _,row in df.iterrows():
            nombre=str(row.get("nombre y apellido","")).strip()
            if not nombre: continue
            c.execute("INSERT INTO clientes(nombre,cuit,telefono,abono) VALUES(%s,%s,%s,%s)",(nombre,str(row.get("cuit","")),str(row.get("telefono","")),row.get("honorario",0)));ok+=1
        conn.commit();conn.close();registrar_auditoria("IMPORTACIÓN",f"{ok} clientes importados")
        return redirect("/clientes")
    body='<h1 class="page-title">Importar Clientes</h1><p class="page-sub">Excel con columnas: <b>nombre y apellido</b>, cuit, telefono, honorario</p><div class="fcard"><h3>📂 Archivo Excel</h3><form method="post" enctype="multipart/form-data"><div class="fg" style="margin-bottom:14px"><label>Archivo .xlsx</label><input type="file" name="archivo" accept=".xlsx,.xls"></div><button class="btn btn-p">Importar</button></form></div>'
    return page("Importar",body)


# ══════════════════════════════════════════════════════
#  CAJA DIARIA
# ══════════════════════════════════════════════════════
MEDIOS_FISICOS = ["Efectivo", "Cheque", "Dólares"]

def _totales_caja(fecha_hoy, usuario):
    """Calcula los totales de pagos del día para un usuario dado."""
    conn = conectar(); c = conn.cursor()
    # Todos los pagos del día de este usuario
    c.execute("""SELECT medio, SUM(monto) FROM pagos
                 WHERE fecha LIKE %s AND emitido_por=%s GROUP BY medio""",
              (f"%{fecha_hoy}%", usuario))
    filas = c.fetchall(); conn.close()
    totales = {"Efectivo": 0, "Cheque": 0, "Dólares": 0,
               "Transferencia → Natasha Carlon": 0,
               "Transferencia → Maira Carlon": 0, "Otro": 0}
    for medio, monto in filas:
        for k in totales:
            if k.lower() in (medio or "").lower():
                totales[k] += monto or 0
                break
        else:
            totales["Otro"] += monto or 0
    totales["total_fisico"] = totales["Efectivo"] + totales["Cheque"] + totales["Dólares"]
    totales["total_general"] = sum(v for k,v in totales.items() if k not in ("total_fisico","total_general"))
    return totales

@app.route("/caja", methods=["GET","POST"])
@login_req
def caja():
    conn = conectar(); c = conn.cursor()
    flash = ""
    usuario = session.get("display","")
    rol     = session.get("rol","secretaria")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    if request.method == "POST":
        accion = request.form.get("accion","")

        if accion == "cerrar_caja":
            # Verificar que no haya cierre ya hoy para este usuario
            c.execute("SELECT id FROM cierres_caja WHERE fecha=%s AND usuario=%s AND cerrado=TRUE",
                      (fecha_hoy, usuario))
            if c.fetchone():
                flash = '<div class="flash ferr">❌ Ya cerraste tu caja hoy</div>'
            else:
                tot = _totales_caja(fecha_hoy, usuario)
                # Obtener detalle de pagos del día
                c.execute("""SELECT p.fecha, cl.nombre, p.monto, p.medio, p.observaciones
                             FROM pagos p JOIN clientes cl ON cl.id=p.cliente_id
                             WHERE p.fecha LIKE %s AND p.emitido_por=%s ORDER BY p.id""",
                          (f"%{fecha_hoy}%", usuario))
                pagos_dia = c.fetchall()
                detalle = " | ".join(f"{p[1]}:{fmt(p[2])}({p[3]})" for p in pagos_dia)

                # Verificar si ya existe registro abierto del día → actualizarlo
                c.execute("SELECT id FROM cierres_caja WHERE fecha=%s AND usuario=%s",
                          (fecha_hoy, usuario))
                existe = c.fetchone()
                if existe:
                    c.execute("""UPDATE cierres_caja SET efectivo=%s,cheque=%s,dolares=%s,
                                 transferencia_nat=%s,transferencia_mai=%s,otro=%s,
                                 total_fisico=%s,total_general=%s,detalle_pagos=%s,
                                 cerrado=TRUE,hora_cierre=%s WHERE id=%s""",
                              (tot["Efectivo"], tot["Cheque"], tot["Dólares"],
                               tot["Transferencia → Natasha Carlon"],
                               tot["Transferencia → Maira Carlon"],
                               tot["Otro"], tot["total_fisico"], tot["total_general"],
                               detalle, datetime.now().strftime("%H:%M"), existe[0]))
                else:
                    c.execute("""INSERT INTO cierres_caja(fecha,usuario,efectivo,cheque,dolares,
                                 transferencia_nat,transferencia_mai,otro,total_fisico,
                                 total_general,detalle_pagos,cerrado,hora_cierre)
                                 VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)""",
                              (fecha_hoy, usuario, tot["Efectivo"], tot["Cheque"],
                               tot["Dólares"], tot["Transferencia → Natasha Carlon"],
                               tot["Transferencia → Maira Carlon"], tot["Otro"],
                               tot["total_fisico"], tot["total_general"], detalle,
                               datetime.now().strftime("%H:%M")))
                conn.commit()
                registrar_auditoria("CIERRE DE CAJA",
                    f"Físico:{fmt(tot['total_fisico'])} | Total:{fmt(tot['total_general'])} | "
                    f"Efectivo:{fmt(tot['Efectivo'])} | Cheque:{fmt(tot['Cheque'])} | "
                    f"Dólares:{fmt(tot['Dólares'])}")
                flash = f'<div class="flash fok">✅ Caja cerrada correctamente · {datetime.now().strftime("%H:%M")}</div>'

    # Calcular totales del día actual para el usuario actual (vista previa)
    tot_hoy = _totales_caja(fecha_hoy, usuario)

    # Verificar si ya cerró hoy
    c.execute("SELECT hora_cierre,cerrado FROM cierres_caja WHERE fecha=%s AND usuario=%s ORDER BY id DESC LIMIT 1",
              (fecha_hoy, usuario))
    estado_hoy = c.fetchone()
    ya_cerro = estado_hoy and estado_hoy[1]

    # Pagos del día del usuario actual
    c.execute("""SELECT p.fecha, cl.nombre, p.monto, p.medio, p.observaciones, p.facturado
                 FROM pagos p JOIN clientes cl ON cl.id=p.cliente_id
                 WHERE p.fecha LIKE %s AND p.emitido_por=%s ORDER BY p.id DESC""",
              (f"%{fecha_hoy}%", usuario))
    pagos_hoy = c.fetchall()

    # Historial de cierres (propios)
    c.execute("""SELECT fecha,hora_cierre,efectivo,cheque,dolares,transferencia_nat,
                        transferencia_mai,otro,total_fisico,total_general,cerrado
                 FROM cierres_caja WHERE usuario=%s ORDER BY id DESC LIMIT 20""", (usuario,))
    historial_caja = c.fetchall()

    # SOLO ADMIN: ver todos los cierres del día
    cierres_todos = []
    if rol == "admin":
        c.execute("""SELECT usuario,hora_cierre,efectivo,cheque,dolares,transferencia_nat,
                            transferencia_mai,otro,total_fisico,total_general,cerrado,fecha
                     FROM cierres_caja WHERE fecha=%s ORDER BY id DESC""", (fecha_hoy,))
        cierres_todos = c.fetchall()
        # Totales del día de TODOS para admin
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE fecha LIKE %s",(f"%{fecha_hoy}%",))
        total_dia_admin = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE fecha LIKE %s AND medio NOT ILIKE '%transferencia%'",(f"%{fecha_hoy}%",))
        fisico_dia_admin = c.fetchone()[0]

    conn.close()

    # HTML pagos del día
    filas_pagos = ""
    for p in pagos_hoy:
        fact_b = '🧾' if p[5] else ''
        filas_pagos += f"""<tr>
          <td class="mu">{p[0].split()[1] if ' ' in p[0] else p[0]}</td>
          <td class="nm">{p[1]}</td>
          <td style="font-weight:600;color:var(--success)">{fmt(p[2])}</td>
          <td><span class="bmedio">{p[3]}</span></td>
          <td class="mu">{p[4] or '—'} {fact_b}</td>
        </tr>"""

    # Tarjetas de resumen del día
    def caja_item(label, valor, cls=""):
        return f'<div class="caja-item {cls}"><div class="ci-label">{label}</div><div class="ci-val">{fmt(valor)}</div></div>'

    items_resumen = (
        caja_item("💵 Efectivo", tot_hoy["Efectivo"], "efectivo") +
        caja_item("📋 Cheque",   tot_hoy["Cheque"],   "cheque")  +
        caja_item("💲 Dólares",  tot_hoy["Dólares"],  "dolares") +
        caja_item("🏦 Transf. Natasha", tot_hoy["Transferencia → Natasha Carlon"], "transferencia") +
        caja_item("🏦 Transf. Maira",   tot_hoy["Transferencia → Maira Carlon"],   "transferencia") +
        caja_item("💰 TOTAL FÍSICO", tot_hoy["total_fisico"], "total-fisico")
    )

    estado_html = ""
    if ya_cerro:
        estado_html = f'<span class="estado-cerrada">✓ Caja cerrada a las {estado_hoy[0]}</span>'
        btn_cierre = '<button class="btn btn-o" disabled style="opacity:.5">✓ Ya cerrada</button>'
    else:
        estado_html = '<span class="estado-abierta">● Caja abierta</span>'
        btn_cierre = f'''<form method="post" onsubmit="return confirm('¿Cerrar la caja del día? Esta acción queda registrada.')">
          <input type="hidden" name="accion" value="cerrar_caja">
          <button type="submit" class="btn btn-r">🔒 Cerrar Caja Hoy</button>
        </form>'''

    # Historial de cierres propios
    hist_rows = ""
    for h in historial_caja:
        estado_c = '<span class="estado-cerrada" style="font-size:.68rem">✓ Cerrada</span>' if h[10] else '<span class="estado-abierta" style="font-size:.68rem">● Abierta</span>'
        hist_rows += f"""<div class="caja-row {"cerrada" if h[10] else ""}">
          <div class="caja-header">
            <div>
              <span class="caja-user">📅 {h[0]}</span>
              <span class="caja-fecha"> · Cierre: {h[1] or '—'}</span>
            </div>
            {estado_c}
          </div>
          <div class="caja-medios">
            {caja_item("Efectivo", h[2], "efectivo")}
            {caja_item("Cheque", h[3], "cheque")}
            {caja_item("Dólares", h[4], "dolares")}
            {caja_item("T. Natasha", h[5], "transferencia")}
            {caja_item("T. Maira", h[6], "transferencia")}
            {caja_item("FÍSICO", h[8], "total-fisico")}
          </div>
        </div>"""

    # Panel admin: cierres de todos hoy
    admin_section = ""
    if rol == "admin":
        cierres_html = ""
        for ct in cierres_todos:
            est = '<span class="estado-cerrada" style="font-size:.68rem">✓ Cerrada</span>' if ct[10] else '<span class="estado-abierta" style="font-size:.68rem">● Abierta</span>'
            cierres_html += f"""<div class="caja-row">
              <div class="caja-header">
                <div>
                  <span class="caja-user">👤 {ct[0]}</span>
                  <span class="caja-fecha"> · Cierre: {ct[1] or 'sin cerrar'}</span>
                </div>{est}
              </div>
              <div class="caja-medios">
                {caja_item("Efectivo", ct[2], "efectivo")}
                {caja_item("Cheque", ct[3], "cheque")}
                {caja_item("Dólares", ct[4], "dolares")}
                {caja_item("T. Natasha", ct[5], "transferencia")}
                {caja_item("T. Maira", ct[6], "transferencia")}
                {caja_item("FÍSICO", ct[8], "total-fisico")}
                {caja_item("TOTAL DÍA", ct[9], "total-fisico")}
              </div>
            </div>"""

        admin_section = f"""
        <div class="fcard" style="border-left:4px solid var(--accent)">
          <h3>👑 Vista Admin — Todos los cierres de hoy ({fecha_hoy})</h3>
          <div class="stats" style="margin-bottom:16px">
            <div class="scard g"><div class="sicon">💰</div>
              <div class="slabel">Total cobrado hoy</div>
              <div class="sval">{fmt(total_dia_admin)}</div>
            </div>
            <div class="scard o"><div class="sicon">💵</div>
              <div class="slabel">Total físico hoy</div>
              <div class="sval">{fmt(fisico_dia_admin)}</div>
            </div>
          </div>
          {cierres_html or '<p style="color:var(--muted);font-size:.84rem">Ninguna secretaria cerró caja hoy todavía</p>'}
          <div style="margin-top:12px">
            <a href="/caja/historial" class="btn btn-b btn-sm">📋 Ver historial completo</a>
          </div>
        </div>"""

    body = f"""
    <h1 class="page-title">Caja Diaria</h1>
    <p class="page-sub">{fecha_hoy} · {usuario} · {estado_html}</p>
    {flash}

    <div class="fcard">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:16px">
        <h3 style="border:none;padding:0;margin:0">💰 Cobros del día — {fecha_hoy}</h3>
        {btn_cierre}
      </div>
      <div class="caja-medios" style="margin-bottom:16px">{items_resumen}</div>
      {'<div class="dtable"><table><thead><tr><th>Hora</th><th>Cliente</th><th>Monto</th><th>Medio</th><th>Obs.</th></tr></thead><tbody>'+filas_pagos+'</tbody></table></div>' if pagos_hoy else '<p style="color:var(--muted);font-size:.84rem;padding:12px 0">Sin cobros registrados hoy</p>'}
    </div>

    {admin_section}

    <div class="fcard">
      <h3>📋 Mis cierres anteriores</h3>
      {hist_rows or '<p style="color:var(--muted);font-size:.84rem">Sin cierres registrados</p>'}
    </div>"""
    return page("Caja", body, "Caja")


@app.route("/caja/historial")
@admin_req
def caja_historial():
    conn = conectar(); c = conn.cursor()

    # Filtro de fecha
    fecha_f = request.args.get("fecha","")
    usuario_f = request.args.get("usuario","")

    query = "SELECT usuario,fecha,hora_cierre,efectivo,cheque,dolares,transferencia_nat,transferencia_mai,otro,total_fisico,total_general,cerrado FROM cierres_caja WHERE 1=1"
    params = []
    if fecha_f:
        query += " AND fecha=%s"; params.append(fecha_f)
    if usuario_f:
        query += " AND usuario=%s"; params.append(usuario_f)
    query += " ORDER BY id DESC LIMIT 100"

    c.execute(query, params)
    cierres = c.fetchall()

    # Totales por usuario (histórico)
    c.execute("""SELECT usuario, SUM(efectivo), SUM(cheque), SUM(dolares),
                        SUM(transferencia_nat), SUM(transferencia_mai), SUM(total_fisico), SUM(total_general)
                 FROM cierres_caja WHERE cerrado=TRUE GROUP BY usuario ORDER BY usuario""")
    resumen_usuarios = c.fetchall()

    # Lista de usuarios para el filtro
    c.execute("SELECT DISTINCT usuario FROM cierres_caja ORDER BY usuario")
    usuarios_lista = [r[0] for r in c.fetchall()]
    conn.close()

    def caja_item(label, valor, cls=""):
        return f'<div class="caja-item {cls}"><div class="ci-label">{label}</div><div class="ci-val">{fmt(valor)}</div></div>'

    filas_hist = ""
    for ct in cierres:
        est = '<span class="estado-cerrada" style="font-size:.68rem">✓ Cerrada</span>' if ct[11] else '<span class="estado-abierta" style="font-size:.68rem">● Sin cerrar</span>'
        filas_hist += f"""<div class="caja-row {"cerrada" if ct[11] else ""}">
          <div class="caja-header">
            <div>
              <span class="caja-user">👤 {ct[0]}</span>
              <span class="caja-fecha"> · {ct[1]} · cierre: {ct[2] or '—'}</span>
            </div>{est}
          </div>
          <div class="caja-medios">
            {caja_item("Efectivo", ct[3], "efectivo")}
            {caja_item("Cheque", ct[4], "cheque")}
            {caja_item("Dólares", ct[5], "dolares")}
            {caja_item("T. Natasha", ct[6], "transferencia")}
            {caja_item("T. Maira", ct[7], "transferencia")}
            {caja_item("FÍSICO", ct[9], "total-fisico")}
            {caja_item("TOTAL", ct[10], "total-fisico")}
          </div>
        </div>"""

    # Resumen por usuario
    res_html = ""
    for ru in resumen_usuarios:
        res_html += f"""<div class="caja-row">
          <div class="caja-header" style="margin-bottom:10px">
            <span class="caja-user">👤 {ru[0]}</span>
          </div>
          <div class="caja-medios">
            {caja_item("Efectivo", ru[1] or 0, "efectivo")}
            {caja_item("Cheque", ru[2] or 0, "cheque")}
            {caja_item("Dólares", ru[3] or 0, "dolares")}
            {caja_item("T. Natasha", ru[4] or 0, "transferencia")}
            {caja_item("T. Maira", ru[5] or 0, "transferencia")}
            {caja_item("FÍSICO TOTAL", ru[6] or 0, "total-fisico")}
            {caja_item("TOTAL GENERAL", ru[7] or 0, "total-fisico")}
          </div>
        </div>"""

    usu_opts = '<option value="">Todos</option>' + "".join(f'<option value="{u}" {"selected" if u==usuario_f else ""}>{u}</option>' for u in usuarios_lista)

    body = f"""
    <a href="/caja" class="btn btn-o btn-sm" style="margin-bottom:18px">← Volver a Caja</a>
    <h1 class="page-title">Historial de Caja</h1>
    <p class="page-sub">Registro completo de cierres de caja por secretaria</p>

    <div class="fcard">
      <h3>📊 Acumulado por Secretaria</h3>
      {res_html or '<p style="color:var(--muted);font-size:.84rem">Sin cierres registrados</p>'}
    </div>

    <div class="fcard">
      <h3>🔍 Filtrar registros</h3>
      <form method="get" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end">
        <div class="fg"><label>Fecha (dd/mm/yyyy)</label>
          <input name="fecha" value="{fecha_f}" placeholder="dd/mm/yyyy" style="width:140px">
        </div>
        <div class="fg"><label>Secretaria</label>
          <select name="usuario" style="width:160px">{usu_opts}</select>
        </div>
        <button class="btn btn-p btn-sm">Filtrar</button>
        <a href="/caja/historial" class="btn btn-o btn-sm">Limpiar</a>
      </form>
    </div>

    {filas_hist or '<p style="color:var(--muted);text-align:center;padding:28px">Sin registros</p>'}
    """
    return page("Historial de Caja", body, "Caja")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
 
SYSTEM_ASISTENTE = """Sos el asistente virtual del Estudio Contable Carlon, ubicado en Quimilí, Santiago del Estero, Argentina.
 
Tu función es ayudar al personal del estudio (secretarias y contadoras) con:
- Dudas contables e impositivas generales
- Instrucciones para presentar declaraciones juradas (DDJJ) en AFIP/ARCA
- IVA, Ganancias, Bienes Personales, Monotributo, Empleados en Relación de Dependencia
- Vencimientos y fechas importantes de AFIP
- Consultas sobre el sistema interno (cómo registrar pagos, agregar clientes, cerrar caja, generar recibos, etc.)
- Terminología contable e impositiva
- Procedimientos de facturación electrónica en ARCA
 
RESTRICCIONES ABSOLUTAS — NUNCA respondas sobre:
- Cómo editar, modificar, corregir o cambiar pagos ya registrados
- Cómo eliminar pagos o movimientos de caja
- Cómo revertir o anular cobros en el sistema
- Cómo modificar importes ya cargados en la base de datos
- Cualquier instrucción que implique alterar registros financieros existentes del estudio
 
Si te preguntan algo de esas categorías, respondé exactamente: 
"Esa consulta debe realizarse directamente con el administrador del sistema. Por razones de seguridad y auditoría, no puedo dar instrucciones sobre modificación de registros financieros."
 
Respondé siempre en español, de forma clara y concisa. Usá ejemplos prácticos cuando sea útil.
Para consultas sobre AFIP/ARCA, mencioná siempre que los procedimientos pueden cambiar y recomendá verificar en afip.gob.ar."""
 
@app.route("/asistente", methods=["POST"])
@login_req
def asistente():
    try:
        data = request.get_json()
        mensajes = data.get("mensajes", [])
        
        if not mensajes:
            return json.dumps({"error": "Sin mensajes"}), 400
        
        # Limitar historial a últimos 10 mensajes para no exceder tokens
        mensajes = mensajes[-10:]
        
        # Validar que solo sean roles permitidos
        mensajes_limpios = [
            {"role": m["role"], "content": str(m["content"])[:2000]}
            for m in mensajes
            if m.get("role") in ("user", "assistant")
        ]
        
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": SYSTEM_ASISTENTE,
            "messages": mensajes_limpios
        }).encode("utf-8")
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            resultado = json.loads(resp.read().decode("utf-8"))
        
        texto = resultado["content"][0]["text"]
        
        # Registrar uso en auditoría (sin guardar el contenido por privacidad)
        registrar_auditoria("ASISTENTE IA", f"Consulta de {session.get('display','')}")
        
        return json.dumps({"respuesta": texto}), 200, {"Content-Type": "application/json"}
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        return json.dumps({"error": f"API error: {e.code}"}), 500, {"Content-Type": "application/json"}
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"}
 
 
# ─────────────────────────────────────────────────────
# PARTE 3: HTML del widget flotante
# Reemplazar la función nav_html() existente con esta versión
# que incluye el botón flotante y el panel del chat
# ─────────────────────────────────────────────────────
 
def nav_html(active=""):
    user = session.get("user", "")
    rol = session.get("rol", "secretaria")
    disp = session.get("display", user)
    links_admin = [("/panel","Panel"),("/clientes","Clientes"),("/deudas","Deudores"),
                   ("/gastos","Gastos"),("/caja","Caja"),("/reportes","Reportes"),("/agenda","Agenda"),("/usuarios","Usuarios")]
    links_sec = [("/clientes","Clientes"),("/deudas","Deudores"),("/gastos","Gastos"),("/caja","Caja"),("/agenda","Agenda")]
    links = links_admin if rol == "admin" else links_sec
    items = "".join(f'<a href="{h}" class="{"act" if active==l else ""}">{l}</a>' for h,l in links)
    items += '<a href="/logout" class="logout">Salir</a>'
    badge = f'<span class="rbadge {"admin" if rol=="admin" else "sec"}">{"Admin" if rol=="admin" else "Sec."}</span>'
 
    # Widget del asistente IA
    asistente_widget = """
<div id="ai-btn" onclick="toggleChat()" style="position:fixed;bottom:24px;right:24px;z-index:1000;width:52px;height:52px;border-radius:50%;background:#1A3A2A;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 16px rgba(0,0,0,0.25);transition:transform .2s" title="Asistente IA">
  <span style="font-size:22px">🤖</span>
  <span id="ai-badge" style="display:none;position:absolute;top:-3px;right:-3px;background:#E24B4A;color:#fff;font-size:10px;font-weight:700;padding:2px 5px;border-radius:10px">!</span>
</div>
 
<div id="ai-panel" style="display:none;position:fixed;bottom:88px;right:24px;z-index:999;width:360px;max-width:calc(100vw - 32px);background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18);overflow:hidden;flex-direction:column;font-family:'DM Sans',sans-serif">
  
  <div style="background:#1A3A2A;padding:14px 16px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:10px">
      <div style="width:36px;height:36px;border-radius:50%;background:#C8A96E;display:flex;align-items:center;justify-content:center;font-size:18px">🤖</div>
      <div>
        <div style="color:#fff;font-weight:600;font-size:.9rem">Asistente Estudio Carlon</div>
        <div style="color:rgba(255,255,255,.55);font-size:.72rem;display:flex;align-items:center;gap:4px">
          <span style="width:6px;height:6px;border-radius:50%;background:#4ade80;display:inline-block"></span>
          En línea · IA
        </div>
      </div>
    </div>
    <button onclick="toggleChat()" style="background:none;border:none;color:rgba(255,255,255,.7);cursor:pointer;font-size:18px;padding:4px;line-height:1">✕</button>
  </div>
  
  <div id="ai-msgs" style="height:320px;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#F7F5F0">
    <div style="background:#fff;border-radius:4px 14px 14px 14px;padding:10px 13px;font-size:.83rem;color:#1C1C1C;max-width:88%;line-height:1.55;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
      ¡Hola! Soy el asistente del Estudio. Puedo ayudarte con dudas contables, impositivas, declaraciones juradas, AFIP y más.<br><br>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px">
        <button onclick="quickQ(this)" data-q="¿Cómo presento el IVA en AFIP?" style="background:#F0EDE8;border:1px solid #E4DDD0;border-radius:20px;padding:4px 10px;font-size:.74rem;cursor:pointer;color:#1A3A2A">IVA en AFIP</button>
        <button onclick="quickQ(this)" data-q="¿Cómo registro un empleado en AFIP?" style="background:#F0EDE8;border:1px solid #E4DDD0;border-radius:20px;padding:4px 10px;font-size:.74rem;cursor:pointer;color:#1A3A2A">Empleado en AFIP</button>
        <button onclick="quickQ(this)" data-q="¿Cuándo vencen las declaraciones juradas?" style="background:#F0EDE8;border:1px solid #E4DDD0;border-radius:20px;padding:4px 10px;font-size:.74rem;cursor:pointer;color:#1A3A2A">Vencimientos DDJJ</button>
        <button onclick="quickQ(this)" data-q="¿Cómo facturo en ARCA?" style="background:#F0EDE8;border:1px solid #E4DDD0;border-radius:20px;padding:4px 10px;font-size:.74rem;cursor:pointer;color:#1A3A2A">Facturar en ARCA</button>
      </div>
    </div>
  </div>
  
  <div style="padding:10px 12px;background:#fff;border-top:1px solid #E4DDD0;display:flex;gap:8px;align-items:flex-end">
    <textarea id="ai-input" placeholder="Escribí tu consulta..." rows="1"
      style="flex:1;border:1.5px solid #E4DDD0;border-radius:12px;padding:8px 12px;font-family:'DM Sans',sans-serif;font-size:.84rem;resize:none;outline:none;line-height:1.45;max-height:100px;overflow-y:auto;background:#F7F5F0"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAI()}"
      oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
    <button onclick="sendAI()" id="ai-send" style="width:36px;height:36px;border-radius:50%;background:#1A3A2A;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:opacity .2s">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="white"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
    </button>
  </div>
</div>
 
<script>
var aiHistorial = [];
var aiAbierto = false;
 
function toggleChat() {
  aiAbierto = !aiAbierto;
  var p = document.getElementById('ai-panel');
  p.style.display = aiAbierto ? 'flex' : 'none';
  if(aiAbierto) {
    document.getElementById('ai-badge').style.display = 'none';
    setTimeout(function(){ document.getElementById('ai-input').focus(); }, 100);
  }
}
 
function addMsgAI(texto, tipo) {
  var box = document.getElementById('ai-msgs');
  var d = document.createElement('div');
  if(tipo === 'user') {
    d.style.cssText = 'background:#1A3A2A;color:#fff;border-radius:14px 4px 14px 14px;padding:9px 13px;font-size:.83rem;max-width:88%;align-self:flex-end;margin-left:auto;line-height:1.55;white-space:pre-wrap';
  } else {
    d.style.cssText = 'background:#fff;border-radius:4px 14px 14px 14px;padding:10px 13px;font-size:.83rem;color:#1C1C1C;max-width:88%;line-height:1.55;box-shadow:0 1px 4px rgba(0,0,0,0.06);white-space:pre-wrap';
  }
  d.textContent = texto;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}
 
function showTypingAI() {
  var box = document.getElementById('ai-msgs');
  var t = document.createElement('div');
  t.id = 'ai-typing';
  t.style.cssText = 'display:flex;align-items:center;gap:4px;padding:10px 13px;background:#fff;border-radius:4px 14px 14px 14px;width:52px;box-shadow:0 1px 4px rgba(0,0,0,0.06)';
  t.innerHTML = '<span style="width:6px;height:6px;border-radius:50%;background:#C8A96E;animation:aib 1.2s infinite"></span><span style="width:6px;height:6px;border-radius:50%;background:#C8A96E;animation:aib 1.2s .2s infinite"></span><span style="width:6px;height:6px;border-radius:50%;background:#C8A96E;animation:aib 1.2s .4s infinite"></span>';
  box.appendChild(t);
  box.scrollTop = box.scrollHeight;
}
 
function quickQ(btn) {
  var q = btn.getAttribute('data-q');
  document.getElementById('ai-input').value = q;
  sendAI();
}
 
function sendAI() {
  var inp = document.getElementById('ai-input');
  var txt = inp.value.trim();
  if(!txt) return;
  inp.value = '';
  inp.style.height = 'auto';
  
  addMsgAI(txt, 'user');
  aiHistorial.push({role:'user', content: txt});
  
  var btn = document.getElementById('ai-send');
  btn.style.opacity = '0.4';
  btn.disabled = true;
  showTypingAI();
  
  fetch('/asistente', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mensajes: aiHistorial})
  })
  .then(function(r){ return r.json(); })
  .then(function(data) {
    var t = document.getElementById('ai-typing');
    if(t) t.remove();
    btn.style.opacity = '1';
    btn.disabled = false;
    if(data.respuesta) {
      addMsgAI(data.respuesta, 'bot');
      aiHistorial.push({role:'assistant', content: data.respuesta});
    } else {
      addMsgAI('Hubo un error. Intentá de nuevo.', 'bot');
    }
  })
  .catch(function() {
    var t = document.getElementById('ai-typing');
    if(t) t.remove();
    btn.style.opacity = '1';
    btn.disabled = false;
    addMsgAI('Sin conexión. Verificá tu red e intentá de nuevo.', 'bot');
  });
}
 
// Animación del typing
var style = document.createElement('style');
style.textContent = '@keyframes aib{0%,80%,100%{opacity:.2}40%{opacity:1}}';
document.head.appendChild(style);
</script>
"""
    return f'<nav><span class="brand">✦ Estudio Carlon</span><div class="nav-links">{items}</div><div class="user-pill">👤 {disp} {badge}</div></nav>{asistente_widget}


@app.route("/agenda", methods=["GET"])
@login_req
def agenda():
    import json as _json
    mes = int(request.args.get("mes", datetime.now().month))
    anio = int(request.args.get("anio", datetime.now().year))
 
    conn = conectar(); c = conn.cursor()
 
    # Traer estados guardados para este mes/año
    c.execute("""SELECT vencimiento_id, estado, nota, usuario, fecha_actualizacion
                 FROM agenda_vencimientos WHERE mes=%s AND anio=%s""", (mes, anio))
    estados_db = {r[0]: {"estado": r[1], "nota": r[2] or "", "usuario": r[3], "fecha": r[4]} for r in c.fetchall()}
 
    # Alertas: vencimientos próximos (próximos 5 días) o vencidos sin presentar
    hoy = datetime.now()
    alertas = []
    for v in VENCIMIENTOS_IMPOSITIVOS:
        est = estados_db.get(v["id"], {}).get("estado", "pendiente")
        if est == "presentado":
            continue
        try:
            fecha_v = datetime(anio, mes, v["dia"])
            diff = (fecha_v - hoy).days
            if diff < 0:
                alertas.append(f"⚠ {v['nombre']} venció hace {abs(diff)} días sin presentar")
            elif diff <= 5:
                alertas.append(f"🔔 {v['nombre']} vence en {'HOY' if diff==0 else str(diff)+' días'}")
        except:
            pass
 
    # Estadísticas
    stats = {"total": len(VENCIMIENTOS_IMPOSITIVOS), "presentado": 0, "borrador": 0, "pendiente": 0, "observado": 0}
    for v in VENCIMIENTOS_IMPOSITIVOS:
        est = estados_db.get(v["id"], {}).get("estado", "pendiente")
        stats[est] = stats.get(est, 0) + 1
 
    # Actividad reciente
    c.execute("""SELECT vencimiento_id, estado, nota, usuario, fecha_actualizacion
                 FROM agenda_vencimientos WHERE mes=%s AND anio=%s ORDER BY id DESC LIMIT 10""", (mes, anio))
    actividad = c.fetchall()
    conn.close()
 
    MESES_ESP = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
 
    # Navegación mes anterior/siguiente
    mes_ant = mes - 1 if mes > 1 else 12
    anio_ant = anio if mes > 1 else anio - 1
    mes_sig = mes + 1 if mes < 12 else 1
    anio_sig = anio if mes < 12 else anio + 1
 
    # HTML de vencimientos
    filas = ""
    for v in sorted(VENCIMIENTOS_IMPOSITIVOS, key=lambda x: x["dia"]):
        est_data = estados_db.get(v["id"], {"estado": "pendiente", "nota": "", "usuario": "", "fecha": ""})
        est = est_data["estado"]
        nota = est_data["nota"]
        ult_usuario = est_data["usuario"]
        ult_fecha = est_data["fecha"]
 
        try:
            fecha_v = datetime(anio, mes, v["dia"])
            diff = (fecha_v - hoy).days
        except:
            diff = 99
 
        # Clase de la card
        if est == "presentado":
            clase = "ok"
        elif diff < 0:
            clase = "vencido"
        elif diff == 0:
            clase = "hoy"
        elif diff <= 5:
            clase = "proximo"
        else:
            clase = ""
 
        # Badge días
        if est == "presentado":
            dias_badge = '<span style="font-size:.71rem;padding:2px 8px;border-radius:10px;background:#E1F5EE;color:#085041;font-weight:600">✓ Presentado</span>'
        elif diff < 0:
            dias_badge = f'<span style="font-size:.71rem;padding:2px 8px;border-radius:10px;background:#FCEBEB;color:#791F1F;font-weight:600">Venció hace {abs(diff)}d</span>'
        elif diff == 0:
            dias_badge = '<span style="font-size:.71rem;padding:2px 8px;border-radius:10px;background:#FAEEDA;color:#633806;font-weight:600">⚡ Vence HOY</span>'
        elif diff <= 5:
            dias_badge = f'<span style="font-size:.71rem;padding:2px 8px;border-radius:10px;background:#E6F1FB;color:#0C447C;font-weight:600">En {diff} días</span>'
        else:
            dias_badge = f'<span style="font-size:.71rem;padding:2px 8px;border-radius:10px;background:var(--bg);color:var(--muted)">En {diff} días</span>'
 
        # Badge estado
        ESTADOS_BADGE = {
            "pendiente":  '<span class="badge" style="background:#fef3cd;color:#9a6700">⏳ Pendiente</span>',
            "borrador":   '<span class="badge" style="background:#dce8ff;color:#1a4a8a">📝 Borrador</span>',
            "presentado": '<span class="badge" style="background:#d5f5e3;color:#1a7a42">✅ Presentado</span>',
            "observado":  '<span class="badge" style="background:#fde8e8;color:#c0392b">⚠ Observado</span>',
        }
        badge_est = ESTADOS_BADGE.get(est, "")
 
        tipo_badge = f'<span style="font-size:.68rem;padding:2px 7px;border-radius:10px;background:var(--bg);color:var(--muted);border:1px solid var(--border)">{v["tipo"]}</span>'
 
        ult_act = f'<span style="font-size:.68rem;color:var(--muted)">Actualizado por {ult_usuario} · {ult_fecha}</span>' if ult_usuario else ""
 
        ESTADOS_OPTS = ["pendiente", "borrador", "presentado", "observado"]
        ESTADOS_LABELS = {"pendiente": "⏳ Pendiente", "borrador": "📝 En borrador", "presentado": "✅ Presentado", "observado": "⚠ Observado por AFIP"}
        opts = "".join(f'<option value="{e}" {"selected" if e==est else ""}>{ESTADOS_LABELS[e]}</option>' for e in ESTADOS_OPTS)
 
        border_color = {"ok": "var(--success)", "vencido": "var(--danger)", "hoy": "var(--warning)", "proximo": "var(--info)"}.get(clase, "var(--border)")
 
        filas += f"""
        <div style="background:var(--card);border-radius:var(--r);border:0.5px solid var(--border);border-left:3px solid {border_color};padding:14px 16px;margin-bottom:9px">
          <div style="display:flex;align-items:flex-start;gap:12px">
            <div style="min-width:46px;text-align:center;background:var(--bg);border-radius:var(--r);padding:6px 8px">
              <div style="font-family:'DM Serif Display',serif;font-size:1.3rem;color:var(--primary);line-height:1">{v["dia"]}</div>
              <div style="font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px">{MESES_ESP[mes][:3]}</div>
            </div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:600;color:var(--primary);font-size:.93rem">{v["nombre"]}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:5px">
                {tipo_badge}{dias_badge}{badge_est}
              </div>
              <div style="font-size:.75rem;color:var(--muted);margin-top:4px">{v["detalle"]}</div>
              {f'<div style="margin-top:4px">{ult_act}</div>' if ult_act else ""}
 
              <form method="post" action="/agenda/actualizar" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border)">
                <input type="hidden" name="venc_id" value="{v["id"]}">
                <input type="hidden" name="mes" value="{mes}">
                <input type="hidden" name="anio" value="{anio}">
                <div style="display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap">
                  <div class="fg" style="min-width:180px">
                    <label>Estado</label>
                    <select name="estado" style="font-size:.82rem">{opts}</select>
                  </div>
                  <div class="fg" style="flex:1;min-width:200px">
                    <label>Nota / avance</label>
                    <input name="nota" value="{nota}" placeholder="Ej: borrador listo, N° presentación 123456..." style="font-size:.82rem">
                  </div>
                  <button type="submit" class="btn btn-p btn-sm">Guardar</button>
                </div>
              </form>
            </div>
          </div>
        </div>"""
 
    # HTML actividad reciente
    act_html = ""
    NOMBRES_V = {v["id"]: v["nombre"] for v in VENCIMIENTOS_IMPOSITIVOS}
    for a in actividad:
        ESTADOS_LABELS2 = {"pendiente": "Pendiente", "borrador": "En borrador", "presentado": "Presentado", "observado": "Observado"}
        act_html += f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[4]}</span><span class="log-user">{a[3]}</span><span class="log-msg"><b>{NOMBRES_V.get(a[0], a[0])}</b> → {ESTADOS_LABELS2.get(a[1], a[1])}{" · "+a[2] if a[2] else ""}</span></div>'
 
    # Alertas HTML
    alerta_html = ""
    if alertas:
        alerta_html = '<div class="warn-box" style="margin-bottom:16px">' + "<br>".join(alertas) + "</div>"
 
    # Progress bar
    pct_pres = int(stats["presentado"] / stats["total"] * 100) if stats["total"] > 0 else 0
 
    body = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:5px">
      <h1 class="page-title">Agenda de Vencimientos</h1>
      <div style="display:flex;align-items:center;gap:8px">
        <a href="/agenda?mes={mes_ant}&anio={anio_ant}" class="btn btn-o btn-sm">← Anterior</a>
        <span style="font-family:'DM Serif Display',serif;font-size:1.1rem;color:var(--primary);min-width:160px;text-align:center">{MESES_ESP[mes]} {anio}</span>
        <a href="/agenda?mes={mes_sig}&anio={anio_sig}" class="btn btn-o btn-sm">Siguiente →</a>
      </div>
    </div>
    <p class="page-sub">Control de vencimientos impositivos · Santiago del Estero</p>
 
    {alerta_html}
 
    <div class="stats" style="margin-bottom:18px">
      <div class="scard"><div class="sicon">📅</div><div class="slabel">Total</div><div class="sval">{stats["total"]}</div></div>
      <div class="scard g"><div class="sicon">✅</div><div class="slabel">Presentados</div><div class="sval">{stats["presentado"]}</div></div>
      <div class="scard b"><div class="sicon">📝</div><div class="slabel">En borrador</div><div class="sval">{stats["borrador"]}</div></div>
      <div class="scard r"><div class="sicon">⏳</div><div class="slabel">Pendientes</div><div class="sval">{stats["pendiente"]}</div></div>
    </div>
 
    <div class="fcard" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:.82rem">
        <span style="font-weight:600;color:var(--primary)">Progreso del mes</span>
        <span style="color:var(--success);font-weight:700">{pct_pres}% presentado</span>
      </div>
      <div class="progwrap"><div class="progbar" style="width:{pct_pres}%"></div></div>
    </div>
 
    <div style="display:grid;grid-template-columns:1fr 340px;gap:16px;align-items:start" class="twocol">
      <div>{filas}</div>
      <div>
        <div class="fcard" style="margin-bottom:14px">
          <h3>🕓 Actividad reciente</h3>
          {act_html or '<p style="color:var(--muted);font-size:.84rem">Sin actividad este mes</p>'}
        </div>
        <div class="info-box">
          <b>Leyenda de estados:</b><br>
          ⏳ Pendiente — todavía no empezó<br>
          📝 En borrador — en proceso de preparación<br>
          ✅ Presentado — entregado en AFIP/Rentas<br>
          ⚠ Observado — AFIP solicitó corrección
        </div>
      </div>
    </div>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
 
    return page("Agenda de Vencimientos", body, "Agenda")
 
 
@app.route("/agenda/actualizar", methods=["POST"])
@login_req
def agenda_actualizar():
    venc_id = request.form.get("venc_id", "").strip()
    mes = int(request.form.get("mes", datetime.now().month))
    anio = int(request.form.get("anio", datetime.now().year))
    estado = request.form.get("estado", "pendiente")
    nota = request.form.get("nota", "").strip()
 
    # Validar que el venc_id sea uno conocido
    ids_validos = {v["id"] for v in VENCIMIENTOS_IMPOSITIVOS}
    if venc_id not in ids_validos:
        return redirect(f"/agenda?mes={mes}&anio={anio}")
 
    conn = conectar(); c = conn.cursor()
    c.execute("""INSERT INTO agenda_vencimientos(vencimiento_id, mes, anio, estado, nota, usuario, fecha_actualizacion)
                 VALUES(%s,%s,%s,%s,%s,%s,%s)
                 ON CONFLICT(vencimiento_id, mes, anio)
                 DO UPDATE SET estado=%s, nota=%s, usuario=%s, fecha_actualizacion=%s""",
              (venc_id, mes, anio, estado, nota, session.get("display",""), now_ar(),
               estado, nota, session.get("display",""), now_ar()))
    conn.commit(); conn.close()
 
    # Encontrar nombre del vencimiento para auditoría
    nombre_v = next((v["nombre"] for v in VENCIMIENTOS_IMPOSITIVOS if v["id"]==venc_id), venc_id)
    registrar_auditoria("AGENDA ACTUALIZADA", f"{nombre_v} → {estado} | {nota}" if nota else f"{nombre_v} → {estado}")
 
    return redirect(f"/agenda?mes={mes}&anio={anio}")
 
if __name__=="__main__":
    app.run(debug=True)
