from flask import Flask, request, redirect, session, send_file, jsonify
import psycopg2, os, qrcode, json, hashlib, hmac, base64, re, time
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from datetime import datetime, timedelta
from io import BytesIO
from cryptography.fernet import Fernet
import pyotp, urllib.request, urllib.parse

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "estudio_carlon_ultra_secure_2026_#$@!")
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
DB_URL = os.getenv("DB_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
WHATSAPP_NUMERO = os.getenv("WHATSAPP_NUMERO", "3855164943")
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY", "")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", "").encode() if os.getenv("ENCRYPT_KEY") else None

# ── Encriptación de datos sensibles ──────────────────────────────────────────
def get_fernet():
    k = ENCRYPT_KEY
    if not k:
        raw = (app.secret_key + "_enc_salt_carlon_2026").encode()
        k = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(k)

def enc(val):
    if not val: return val
    try: return get_fernet().encrypt(str(val).encode()).decode()
    except: return val

def dec(val):
    if not val: return val
    try: return get_fernet().decrypt(val.encode()).decode()
    except: return val

# ── Envío de alertas WhatsApp via CallMeBot ───────────────────────────────────
def enviar_whatsapp(mensaje):
    try:
        if not CALLMEBOT_APIKEY: return
        num = WHATSAPP_NUMERO.replace("+","").replace(" ","")
        msg_enc = urllib.parse.quote(mensaje)
        url = f"https://api.callmebot.com/whatsapp.php?phone=54{num}&text={msg_enc}&apikey={CALLMEBOT_APIKEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        urllib.request.urlopen(req, timeout=5)
    except: pass

# ── Rate limiting & bloqueo de login ─────────────────────────────────────────
LOGIN_INTENTOS = {}   # {ip: {"count": n, "ts": timestamp, "blocked_until": ts}}
MAX_INTENTOS = 5
BLOQUEO_MINS = 30

def get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()

def verificar_bloqueo_ip(ip):
    d = LOGIN_INTENTOS.get(ip, {})
    bu = d.get("blocked_until", 0)
    if bu and time.time() < bu:
        mins = int((bu - time.time()) / 60) + 1
        return True, mins
    return False, 0

def registrar_intento_fallido(ip):
    now = time.time()
    d = LOGIN_INTENTOS.get(ip, {"count": 0, "ts": now})
    if now - d.get("ts", now) > 3600:
        d = {"count": 0, "ts": now}
    d["count"] += 1
    d["ts"] = now
    if d["count"] >= MAX_INTENTOS:
        d["blocked_until"] = now + BLOQUEO_MINS * 60
        enviar_whatsapp(
            f"⚠️ ALERTA SEGURIDAD - Estudio Carlon\n"
            f"🔴 IP {ip} BLOQUEADA por {MAX_INTENTOS} intentos fallidos\n"
            f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"⏱ Bloqueada por {BLOQUEO_MINS} minutos"
        )
        registrar_evento_seguridad("BLOQUEO_IP", f"IP {ip} bloqueada tras {MAX_INTENTOS} intentos", ip)
    LOGIN_INTENTOS[ip] = d
    return d["count"]

def limpiar_intento(ip):
    if ip in LOGIN_INTENTOS:
        LOGIN_INTENTOS[ip] = {"count": 0, "ts": time.time()}

def desbloquear_ip_admin(ip):
    if ip in LOGIN_INTENTOS:
        LOGIN_INTENTOS[ip] = {"count": 0, "ts": time.time(), "blocked_until": 0}

# ── Bloqueo por país (IPs Argentina) ─────────────────────────────────────────
PAISES_PERMITIDOS = ["AR"]

def verificar_pais(ip):
    try:
        if ip in ("127.0.0.1", "::1", "localhost"): return True
        if ip.startswith("192.168.") or ip.startswith("10."): return True
        url = f"http://ip-api.com/json/{ip}?fields=countryCode"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
        cc = data.get("countryCode", "AR")
        if cc not in PAISES_PERMITIDOS:
            registrar_evento_seguridad("ACCESO_PAIS_BLOQUEADO", f"IP {ip} - País {cc}", ip)
            enviar_whatsapp(f"🌎 ACCESO BLOQUEADO\nIP: {ip} - País: {cc}\nFecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            return False
        return True
    except: return True  # Si falla la consulta, permite (no bloquear por error de API)

# ── Registro de eventos de seguridad ─────────────────────────────────────────
def registrar_evento_seguridad(tipo, detalle, ip="", usuario=""):
    try:
        conn = conectar(); c = conn.cursor()
        c.execute("""INSERT INTO seguridad_eventos(tipo,detalle,ip,usuario,fecha)
                     VALUES(%s,%s,%s,%s,%s)""",
                  (tipo, detalle, ip, usuario or session.get("display",""), now_ar()))
        conn.commit(); conn.close()
    except: pass

MEDIOS_PAGO = ["Transferencia -> Natasha Carlon","Transferencia -> Maira Carlon",
               "Efectivo","Cheque","Dolares","Otro"]
CATEGORIAS_GASTO = ["Sueldo","Luz","Internet","Tarjetas","Gastos de Oficina",
                    "Articulos de Limpieza","Papeleria","Otros"]
VENCIMIENTOS_IMPOSITIVOS = [
    {"id":"ib_cat_a",   "nombre":"Ingresos Brutos - Cat. A", "dia":18,"tipo":"IIBB Sgo.","detalle":"Categoria A - vence el 18 de cada mes"},
    {"id":"ib_cat_b",   "nombre":"Ingresos Brutos - Cat. B", "dia":15,"tipo":"IIBB Sgo.","detalle":"Categoria B - vence el 15 de cada mes"},
    {"id":"iva_ddjj",   "nombre":"IVA - DJ (F.731)",          "dia":20,"tipo":"AFIP",     "detalle":"Formulario 731 - presentacion mensual"},
    {"id":"f931_1",     "nombre":"Aportes F.931 - 1ra quinc.","dia":9, "tipo":"AFIP",     "detalle":"Sueldos 1ra quincena - vence el 9"},
    {"id":"f931_2",     "nombre":"Aportes F.931 - 2da quinc.","dia":11,"tipo":"AFIP",     "detalle":"Sueldos 2da quincena - vence el 11"},
    {"id":"ganancias",  "nombre":"Ganancias - Anticipo",      "dia":23,"tipo":"AFIP",     "detalle":"Anticipo mensual segun cronograma AFIP"},
    {"id":"monotributo","nombre":"Monotributo - Cuota",       "dia":20,"tipo":"AFIP",     "detalle":"Cuota unificada mensual"},
    {"id":"suss_ddjj",  "nombre":"SUSS - DJ",                 "dia":9, "tipo":"AFIP",     "detalle":"Sistema Unico de Seguridad Social"},
    {"id":"rentas_prov","nombre":"Rentas Provinciales",       "dia":20,"tipo":"Rentas SGO","detalle":"Dir. Gral. de Rentas - Sgo. del Estero"},
]

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
.log-dot.red{background:var(--danger)}.log-dot.orange{background:var(--warning)}.log-dot.green{background:var(--success)}
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
.fok{background:#d5f5e3;color:#1a7a42}.ferr{background:#fde8e8;color:#c0392b}
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
.sec-alert{background:#fde8e8;border:1px solid #f5a0a0;border-radius:8px;padding:10px 14px;font-size:.81rem;color:#7a1a1a;margin-bottom:8px}
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
.estado-abierta{display:inline-flex;align-items:center;gap:5px;background:#d5f5e3;color:#1a7a42;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700}
.estado-cerrada{display:inline-flex;align-items:center;gap:5px;background:#f0f0f0;color:#666;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700}
.sec-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:10px;font-size:.68rem;font-weight:700}
.sec-badge.ok{background:#d5f5e3;color:#1a7a42}
.sec-badge.warn{background:#fef3cd;color:#9a6700}
.sec-badge.danger{background:#fde8e8;color:#c0392b}
@media(max-width:680px){.stats{grid-template-columns:1fr 1fr}.arow{flex-direction:column;align-items:flex-start}nav .user-pill{display:none}.wrap{padding:18px 12px}.nav-links a{padding:5px 8px;font-size:.78rem}}
"""

ASISTENTE_JS = """
<div id="ai-btn" onclick="toggleChat()" style="position:fixed;bottom:24px;right:24px;z-index:1000;width:52px;height:52px;border-radius:50%;background:#1A3A2A;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 16px rgba(0,0,0,0.25)">
  <span style="font-size:22px">&#x1F916;</span>
</div>
<div id="ai-panel" style="display:none;position:fixed;bottom:88px;right:24px;z-index:999;width:360px;max-width:calc(100vw - 32px);background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18);overflow:hidden;flex-direction:column">
  <div style="background:#1A3A2A;padding:14px 16px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:10px">
      <div style="width:36px;height:36px;border-radius:50%;background:#C8A96E;display:flex;align-items:center;justify-content:center;font-size:18px">&#x1F916;</div>
      <div>
        <div style="color:#fff;font-weight:600;font-size:.9rem">Asistente Estudio Carlon</div>
        <div style="color:rgba(255,255,255,.55);font-size:.72rem">Consultas del sistema y contables</div>
      </div>
    </div>
    <button onclick="toggleChat()" style="background:none;border:none;color:rgba(255,255,255,.7);cursor:pointer;font-size:18px;padding:4px">&#x2715;</button>
  </div>
  <div id="ai-msgs" style="height:300px;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#F7F5F0">
    <div style="background:#fff;border-radius:4px 14px 14px 14px;padding:11px 13px;font-size:.83rem;color:#1C1C1C;max-width:90%;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
      Hola! Puedo ayudarte con el sistema o con consultas contables. Que necesitas?
    </div>
  </div>
  <div style="padding:10px 12px;background:#fff;border-top:1px solid #E4DDD0;display:flex;gap:8px;align-items:flex-end">
    <textarea id="ai-input" placeholder="Escribi tu consulta..." rows="1"
      style="flex:1;border:1.5px solid #E4DDD0;border-radius:12px;padding:8px 12px;font-family:'DM Sans',sans-serif;font-size:.84rem;resize:none;outline:none;line-height:1.45;max-height:90px;overflow-y:auto;background:#F7F5F0;color:#1C1C1C"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAI()}"
      oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
    <button id="ai-send" onclick="sendAI()" style="width:36px;height:36px;border-radius:50%;background:#1A3A2A;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="white"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
    </button>
  </div>
</div>
<script>
var aiAbierto=false,aiHistorial=[];
function addMsg(txt,tipo){
  var box=document.getElementById('ai-msgs');
  var d=document.createElement('div');
  d.className=tipo==='user'?'':'';
  d.style.cssText=tipo==='user'?'background:#1A3A2A;color:#fff;border-radius:14px 4px 14px 14px;padding:10px 13px;font-size:.83rem;max-width:90%;align-self:flex-end;margin-left:auto':'background:#fff;border-radius:4px 14px 14px 14px;padding:11px 13px;font-size:.83rem;color:#1C1C1C;max-width:90%;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,.06);white-space:pre-wrap';
  d.textContent=txt;box.appendChild(d);box.scrollTop=box.scrollHeight;
}
function sendAI(){
  var inp=document.getElementById('ai-input');var q=inp.value.trim();if(!q)return;
  inp.value='';inp.style.height='auto';addMsg(q,'user');
  var btn=document.getElementById('ai-send');btn.style.opacity='0.4';btn.disabled=true;
  aiHistorial.push({role:'user',content:q});
  fetch('/asistente',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mensajes:aiHistorial})})
  .then(r=>r.json()).then(data=>{
    btn.style.opacity='1';btn.disabled=false;
    if(data.respuesta){addMsg(data.respuesta,'bot');aiHistorial.push({role:'assistant',content:data.respuesta});}
    else addMsg('No puedo responder eso ahora. Busca en AFIP o Google.','bot');
  }).catch(()=>{btn.style.opacity='1';btn.disabled=false;addMsg('Sin conexion.','bot');});
}
function toggleChat(){
  aiAbierto=!aiAbierto;var p=document.getElementById('ai-panel');
  p.style.display=aiAbierto?'flex':'none';
  if(aiAbierto)setTimeout(()=>document.getElementById('ai-input').focus(),100);
}
</script>
"""

def nav_html(active=""):
    user=session.get("user","");rol=session.get("rol","secretaria");disp=session.get("display",user)
    links_admin=[("/panel","Panel"),("/clientes","Clientes"),("/deudas","Deudores"),("/gastos","Gastos"),("/caja","Caja"),("/reportes","Reportes"),("/agenda","Agenda"),("/usuarios","Usuarios"),("/seguridad","🔒 Seguridad"),("/configuracion","⚙️ Config")]
    links_sec=[("/clientes","Clientes"),("/deudas","Deudores"),("/gastos","Gastos"),("/caja","Caja"),("/agenda","Agenda")]
    links=links_admin if rol=="admin" else links_sec
    items="".join(f'<a href="{h}" class="{"act" if active==l else ""}">{l}</a>' for h,l in links)
    items+='<a href="/logout" class="logout">Salir</a>'
    badge=f'<span class="rbadge {"admin" if rol=="admin" else "sec"}">{"Admin" if rol=="admin" else "Sec."}</span>'
    return f'<nav><span class="brand">&#x2726; Estudio Carlon</span><div class="nav-links">{items}</div><div class="user-pill">&#x1F464; {disp} {badge}</div></nav>{ASISTENTE_JS}'

def page(title,body,active=""):
    return f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - Estudio Carlon</title><style>{CSS}</style></head><body>{nav_html(active)}<div class="wrap">{body}</div></body></html>'

def fmt(n):
    try: return f"${float(n):,.0f}".replace(",",".")
    except: return f"${n}"

def now_ar(): return datetime.now().strftime("%d/%m/%Y %H:%M")

def denied():
    b='<div class="denied"><div class="di">&#x1F512;</div><h2>Acceso restringido</h2><p>No tenes permiso para esta seccion.</p><a href="/clientes" class="btn btn-p">Volver</a></div>'
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
    c.execute("CREATE TABLE IF NOT EXISTS usuarios(id SERIAL PRIMARY KEY,usuario TEXT UNIQUE,clave TEXT,rol TEXT DEFAULT 'secretaria',nombre_display TEXT,totp_secret TEXT,totp_habilitado BOOLEAN DEFAULT FALSE,activo BOOLEAN DEFAULT TRUE)")
    c.execute("CREATE TABLE IF NOT EXISTS clientes(id SERIAL PRIMARY KEY,nombre TEXT,cuit TEXT,telefono TEXT,email TEXT,abono REAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS cuentas(id SERIAL PRIMARY KEY,cliente_id INTEGER,periodo TEXT,debe REAL DEFAULT 0,haber REAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS pagos(id SERIAL PRIMARY KEY,cliente_id INTEGER,periodo TEXT,monto REAL,medio TEXT,observaciones TEXT,facturado BOOLEAN DEFAULT FALSE,fecha TEXT,usuario TEXT,emitido_por TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id SERIAL PRIMARY KEY,fecha TEXT,categoria TEXT,descripcion TEXT,monto REAL,usuario TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS auditoria(id SERIAL PRIMARY KEY,fecha TEXT,usuario TEXT,accion TEXT,detalle TEXT,cliente_id INTEGER,cliente_nombre TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS cierres_caja(
        id SERIAL PRIMARY KEY,fecha TEXT,usuario TEXT,
        efectivo REAL DEFAULT 0,cheque REAL DEFAULT 0,dolares REAL DEFAULT 0,
        transferencia_nat REAL DEFAULT 0,transferencia_mai REAL DEFAULT 0,otro REAL DEFAULT 0,
        total_fisico REAL DEFAULT 0,total_general REAL DEFAULT 0,
        detalle_pagos TEXT,cerrado BOOLEAN DEFAULT FALSE,hora_cierre TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS agenda_vencimientos(
        id SERIAL PRIMARY KEY,vencimiento_id TEXT,mes INTEGER,anio INTEGER,
        estado TEXT DEFAULT 'pendiente',nota TEXT DEFAULT '',
        usuario TEXT,fecha_actualizacion TEXT,
        UNIQUE(vencimiento_id,mes,anio))""")
    c.execute("""CREATE TABLE IF NOT EXISTS seguridad_eventos(
        id SERIAL PRIMARY KEY,tipo TEXT,detalle TEXT,ip TEXT,
        usuario TEXT,fecha TEXT,resuelto BOOLEAN DEFAULT FALSE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS ips_bloqueadas(
        id SERIAL PRIMARY KEY,ip TEXT UNIQUE,motivo TEXT,
        fecha TEXT,desbloqueada BOOLEAN DEFAULT FALSE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS config_seguridad(
        id SERIAL PRIMARY KEY,clave TEXT UNIQUE,valor TEXT)""")
    conn.commit()
    # Config por defecto
    defaults = [
        ("max_intentos_login","5"),
        ("bloqueo_mins","30"),
        ("paises_permitidos","AR"),
        ("alerta_whatsapp","1"),
        ("2fa_obligatorio","0"),
        ("session_timeout_mins","120"),
    ]
    for k,v in defaults:
        c.execute("INSERT INTO config_seguridad(clave,valor) VALUES(%s,%s) ON CONFLICT(clave) DO NOTHING",(k,v))
    conn.commit();conn.close()

def actualizar_db():
    conn=conectar();c=conn.cursor()
    for ddl in [
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS abono REAL DEFAULT 0",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_display TEXT",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT DEFAULT 'secretaria'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS totp_secret TEXT",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS totp_habilitado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE",
        "ALTER TABLE auditoria ADD COLUMN IF NOT EXISTS cliente_nombre TEXT",
        "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS observaciones TEXT",
        "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS facturado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE pagos ADD COLUMN IF NOT EXISTS emitido_por TEXT",
    ]:
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
        c.execute("INSERT INTO auditoria(fecha,usuario,accion,detalle,cliente_id,cliente_nombre) VALUES(%s,%s,%s,%s,%s,%s)",
                  (now_ar(),session.get("display",session.get("user","?")),accion,detalle,cliente_id,cliente_nombre))
        conn.commit();conn.close()
    except: pass

def svg_barras(datos,color="#C8A96E"):
    if not datos: return '<p style="color:var(--muted);font-size:.84rem">Sin datos</p>'
    W,H=400,150;mx=max(v for _,v in datos) or 1;n=len(datos)
    gap=int(W/n);bw=int(gap*0.6);bars=labels=vals=""
    for i,(per,val) in enumerate(datos):
        x=int(i*gap+gap*0.2);bh=int(val/mx*(H-30));y=H-20-bh
        bars+=f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="3" fill="{color}" opacity=".85"/>'
        labels+=f'<text x="{x+bw//2}" y="{H-4}" text-anchor="middle" font-size="9" fill="#888">{per}</text>'
        if val>0: vals+=f'<text x="{x+bw//2}" y="{y-4}" text-anchor="middle" font-size="8" fill="{color}" font-weight="600">{fmt(val)}</text>'
    return f'<svg viewBox="0 0 {W} {H}" class="chart-svg">{bars}{labels}{vals}</svg>'

init_db();actualizar_db();generar_deuda_mensual()

# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN con protección
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/", methods=["GET","POST"])
def login():
    ip = get_ip()
    # Anti-bot: rate limit global por IP (10 req/min)
    error = ""

    if request.method == "POST":
        # Verificar bloqueo
        bloqueado, mins = verificar_bloqueo_ip(ip)
        if bloqueado:
            registrar_evento_seguridad("INTENTO_IP_BLOQUEADA", f"IP {ip} intentó acceder bloqueada", ip)
            error = f"IP bloqueada por {mins} minuto(s) por exceso de intentos. Contacta al administrador."
        else:
            user = request.form.get("usuario","").strip()
            clave = request.form.get("clave","")
            totp_code = request.form.get("totp_code","").strip()
            conn = conectar(); c = conn.cursor()
            c.execute("SELECT clave,rol,nombre_display,totp_secret,totp_habilitado,activo FROM usuarios WHERE usuario=%s",(user,))
            data = c.fetchone(); conn.close()
            if data and check_password_hash(data[0], clave):
                if not data[5]:  # activo
                    error = "Usuario desactivado. Contacta al administrador."
                elif data[4] and data[3]:  # 2FA habilitado
                    if not totp_code:
                        # Mostrar campo 2FA
                        session["pending_2fa_user"] = user
                        session["pending_2fa_rol"] = data[1]
                        session["pending_2fa_display"] = data[2] or user
                        return redirect("/verificar_2fa")
                    else:
                        totp = pyotp.TOTP(data[3])
                        if totp.verify(totp_code):
                            limpiar_intento(ip)
                            session["user"]=user;session["rol"]=data[1] or "secretaria"
                            session["display"]=data[2] or user
                            registrar_auditoria("LOGIN","Inicio de sesion con 2FA")
                            registrar_evento_seguridad("LOGIN_OK",f"Login exitoso con 2FA",ip,data[2] or user)
                            return redirect("/panel" if session["rol"]=="admin" else "/clientes")
                        else:
                            error = "Código 2FA incorrecto"
                else:
                    limpiar_intento(ip)
                    session["user"]=user;session["rol"]=data[1] or "secretaria"
                    session["display"]=data[2] or user
                    registrar_auditoria("LOGIN","Inicio de sesion")
                    registrar_evento_seguridad("LOGIN_OK",f"Login exitoso",ip,data[2] or user)
                    return redirect("/panel" if session["rol"]=="admin" else "/clientes")
            else:
                count = registrar_intento_fallido(ip)
                restantes = max(0, MAX_INTENTOS - count)
                registrar_evento_seguridad("LOGIN_FALLIDO",f"Usuario: {user} - IP: {ip}",ip,user)
                if restantes > 0:
                    error = f"Usuario o contraseña incorrectos. Intentos restantes: {restantes}"
                else:
                    error = f"IP bloqueada por {BLOQUEO_MINS} minutos."

    err = f'<div class="flash ferr">{error}</div>' if error else ""
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ingresar</title><style>{CSS}</style></head><body>
<div class="lwrap"><div class="lcard">
<p class="ltitle">Bienvenida</p>
<p class="lsub">Estudio Contable Carlon</p>{err}
<form method="post">
  <div class="fg" style="margin-bottom:12px"><label>Usuario</label>
    <input name="usuario" placeholder="tu usuario" autocomplete="username"></div>
  <div class="fg" style="margin-bottom:18px"><label>Contraseña</label>
    <input name="clave" type="password" placeholder="..." autocomplete="current-password"></div>
  <button class="btn btn-p" style="width:100%;justify-content:center">Ingresar</button>
</form>
</div></div></body></html>'''

@app.route("/verificar_2fa", methods=["GET","POST"])
def verificar_2fa():
    if "pending_2fa_user" not in session:
        return redirect("/")
    error = ""
    if request.method == "POST":
        code = request.form.get("code","").strip()
        user = session["pending_2fa_user"]
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT totp_secret FROM usuarios WHERE usuario=%s",(user,))
        row = c.fetchone(); conn.close()
        if row:
            totp = pyotp.TOTP(row[0])
            if totp.verify(code):
                session["user"] = user
                session["rol"] = session.pop("pending_2fa_rol")
                session["display"] = session.pop("pending_2fa_display")
                session.pop("pending_2fa_user", None)
                registrar_auditoria("LOGIN","Inicio de sesion con 2FA")
                return redirect("/panel" if session["rol"]=="admin" else "/clientes")
            else:
                error = "Código incorrecto"
        else:
            error = "Error de sesión"
    err = f'<div class="flash ferr">{error}</div>' if error else ""
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verificar 2FA</title><style>{CSS}</style></head><body>
<div class="lwrap"><div class="lcard">
<p class="ltitle">🔐 Verificación</p>
<p class="lsub">Ingresá el código de tu app Google Authenticator</p>{err}
<form method="post">
  <div class="fg" style="margin-bottom:18px"><label>Código de 6 dígitos</label>
    <input name="code" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6"
     placeholder="000000" autocomplete="one-time-code" autofocus
     style="font-size:1.4rem;letter-spacing:8px;text-align:center"></div>
  <button class="btn btn-p" style="width:100%;justify-content:center">Verificar</button>
</form>
<div style="margin-top:12px;text-align:center">
  <a href="/" style="color:var(--muted);font-size:.8rem">← Volver al login</a>
</div>
</div></div></body></html>'''

@app.route("/logout")
def logout():
    registrar_auditoria("LOGOUT","Cierre de sesion")
    registrar_evento_seguridad("LOGOUT","Cierre de sesion",get_ip())
    session.clear();return redirect("/")

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL con gráficos Chart.js
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/panel")
@login_req
def panel():
    if session.get("rol")!="admin": return redirect("/clientes")
    conn=conectar();c=conn.cursor()
    c.execute("SELECT COALESCE(SUM(debe),0) FROM cuentas");td=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(haber),0) FROM cuentas");th=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clientes");nc=c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT cliente_id) FROM cuentas WHERE (debe-haber)>0");nd=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos");tg=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Natasha%'");cobro_nat=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE medio ILIKE '%Maira%'");cobro_mai=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clientes WHERE abono IS NULL OR abono=0");n_sin_abono=c.fetchone()[0]
    hoy=datetime.now().strftime("%d/%m/%Y")
    c.execute("SELECT COUNT(DISTINCT usuario) FROM pagos WHERE fecha LIKE %s",(f"%{hoy}%",));sec_cobraron=c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT usuario) FROM cierres_caja WHERE fecha=%s AND cerrado=TRUE",(hoy,));sec_cerraron=c.fetchone()[0]
    cajas_pendientes=max(0,sec_cobraron-sec_cerraron)
    # Alertas de seguridad sin resolver
    c.execute("SELECT COUNT(*) FROM seguridad_eventos WHERE resuelto=FALSE AND tipo IN ('BLOQUEO_IP','ACCESO_PAIS_BLOQUEADO','LOGIN_FALLIDO')");alertas_sec=c.fetchone()[0]
    # Datos para gráficos
    c.execute("SELECT periodo,COALESCE(SUM(haber),0) FROM cuentas GROUP BY periodo ORDER BY SUBSTRING(periodo,4,4) DESC,SUBSTRING(periodo,1,2) DESC LIMIT 8")
    raw_ing=list(reversed(c.fetchall()))
    periodos=[r[0] for r in raw_ing];ingresos_m=[float(r[1]) for r in raw_ing]
    gastos_m=[]
    for per in periodos:
        c.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE fecha LIKE %s",(f"%{per.split('/')[1]}%",))
        gastos_m.append(float(c.fetchone()[0]))
    nat_m,mai_m=[],[]
    for per in periodos:
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE periodo=%s AND medio ILIKE '%%Natasha%%'",(per,));nat_m.append(float(c.fetchone()[0]))
        c.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE periodo=%s AND medio ILIKE '%%Maira%%'",(per,));mai_m.append(float(c.fetchone()[0]))
    c.execute("SELECT medio,COALESCE(SUM(monto),0) FROM pagos GROUP BY medio ORDER BY SUM(monto) DESC")
    medios_raw=c.fetchall();total_med=sum(float(r[1]) for r in medios_raw) or 1
    medios_labels=[r[0] for r in medios_raw];medios_data=[round(float(r[1])/total_med*100,1) for r in medios_raw]
    c.execute("SELECT categoria,COALESCE(SUM(monto),0) FROM gastos GROUP BY categoria ORDER BY SUM(monto) DESC LIMIT 7")
    gastos_cat=c.fetchall();gcat_labels=[r[0] for r in gastos_cat];gcat_data=[float(r[1]) for r in gastos_cat]
    cum_ing,cum_gas=[],[]; si,sg=0.0,0.0
    for i in range(len(ingresos_m)):
        si+=ingresos_m[i];sg+=gastos_m[i];cum_ing.append(round(si));cum_gas.append(round(sg))
    c.execute("SELECT cl.nombre,SUM(cu.debe-cu.haber) d FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id GROUP BY cl.nombre HAVING SUM(cu.debe-cu.haber)>0 ORDER BY d DESC LIMIT 6")
    top=c.fetchall()
    c.execute("SELECT fecha,usuario,accion,detalle,cliente_nombre FROM auditoria ORDER BY id DESC LIMIT 8")
    actividad=c.fetchall();conn.close()
    deuda=td-th;rend=th-tg;pct=int(th/td*100) if td>0 else 0
    total_s=cobro_nat+cobro_mai;pct_nat=int(cobro_nat/total_s*100) if total_s>0 else 50;pct_mai=100-pct_nat
    alertas=""
    if n_sin_abono>0:
        alertas+=f'<div class="warn-box"><b>{n_sin_abono}</b> clientes sin honorario · <a href="/clientes" style="color:#7a5800;font-weight:600">Ver</a></div>'
    if cajas_pendientes>0:
        alertas+=f'<div class="sec-alert"><b>{cajas_pendientes}</b> secretaria(s) sin cerrar caja hoy · <a href="/caja" style="color:#7a1a1a;font-weight:600">Ver caja</a></div>'
    if alertas_sec>0:
        alertas+=f'<div class="sec-alert">🔴 <b>{alertas_sec}</b> alerta(s) de seguridad pendientes · <a href="/seguridad" style="color:#7a1a1a;font-weight:600">Ver seguridad</a></div>'
    mx_deu=top[0][1] if top else 1
    barras_deu="".join(f'<div class="chartrow"><span class="cl" title="{n}">{n}</span><div class="cbg"><div class="cfill" style="width:{int(s/mx_deu*100)}%"></div></div><span class="cv">{fmt(s)}</span></div>' for n,s in top) or '<p style="color:var(--muted);font-size:.84rem;padding:12px 0">Sin deudores</p>'
    act_html="".join(f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[0]}</span><span class="log-user">{a[1]}</span><span class="log-msg"><b>{a[2]}</b> - {a[3]}{" · "+a[4] if a[4] else ""}</span></div>' for a in actividad) or '<p style="color:var(--muted);font-size:.84rem;padding:10px 0">Sin actividad</p>'
    body=f"""
    <h1 class="page-title">Panel General</h1>
    <p class="page-sub">Hola, <b>{session.get("display","")}</b> - {now_ar()}</p>
    {alertas}
    <div class="stats">
      <div class="scard"><div class="sicon">&#x1F4B0;</div><div class="slabel">Total Facturado</div><div class="sval">{fmt(td)}</div></div>
      <div class="scard g"><div class="sicon">&#x2705;</div><div class="slabel">Total Cobrado</div><div class="sval">{fmt(th)}</div></div>
      <div class="scard r"><div class="sicon">&#x1F534;</div><div class="slabel">Deuda Pendiente</div><div class="sval">{fmt(deuda)}</div></div>
      <div class="scard o"><div class="sicon">&#x1F4B8;</div><div class="slabel">Total Gastos</div><div class="sval">{fmt(tg)}</div></div>
      <div class="scard {"g" if rend>=0 else "r"}"><div class="sicon">&#x1F4CA;</div><div class="slabel">Rendimiento Real</div><div class="sval">{fmt(rend)}</div></div>
      <div class="scard b"><div class="sicon">&#x1F465;</div><div class="slabel">Clientes</div><div class="sval">{nc}</div></div>
    </div>
    <div class="fcard" style="margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-weight:600;color:var(--primary)">Cobrado vs Facturado</span>
        <span style="font-weight:700;color:var(--success)">{pct}%</span>
      </div>
      <div class="progwrap"><div class="progbar" style="width:{pct}%"></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="partner-card">
        <div class="partner-name">Natasha Carlon</div>
        <div class="partner-amt" style="color:var(--primary)">{fmt(cobro_nat)}</div>
        <div style="font-size:.72rem;color:var(--muted)">{pct_nat}% del total cobrado</div>
      </div>
      <div class="partner-card">
        <div class="partner-name">Maira Carlon</div>
        <div class="partner-amt" style="color:var(--info)">{fmt(cobro_mai)}</div>
        <div style="font-size:.72rem;color:var(--muted)">{pct_mai}% del total cobrado</div>
      </div>
    </div>
    <div class="fcard" style="margin-bottom:18px">
      <h3>📊 Ingresos vs Gastos — últimos meses</h3>
      <div style="position:relative;height:220px"><canvas id="ch1"></canvas></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0">
        <h3>Cobros por socia</h3>
        <div style="position:relative;height:185px"><canvas id="ch2"></canvas></div>
      </div>
      <div class="fcard" style="margin-bottom:0">
        <h3>Medios de pago</h3>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
          <div style="position:relative;height:160px;width:160px;flex-shrink:0"><canvas id="ch3"></canvas></div>
          <div id="leg3" style="font-size:.74rem;color:var(--muted);display:flex;flex-direction:column;gap:5px"></div>
        </div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0">
        <h3>Gastos por categoría</h3>
        <div id="gcat" style="display:flex;flex-direction:column;gap:7px"></div>
      </div>
      <div class="fcard" style="margin-bottom:0">
        <h3>Rendimiento acumulado</h3>
        <div style="position:relative;height:170px"><canvas id="ch4"></canvas></div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px" class="twocol">
      <div class="fcard" style="margin-bottom:0"><h3>Top Deudores</h3>{barras_deu}</div>
      <div class="fcard" style="margin-bottom:0"><h3>Actividad Reciente</h3>{act_html}</div>
    </div>
    <div class="qa">
      <a href="/clientes" class="btn btn-p">Clientes</a>
      <a href="/deudas" class="btn btn-a">Deudores ({nd})</a>
      <a href="/gastos" class="btn btn-o">Gastos</a>
      <a href="/caja" class="btn btn-o">Caja</a>
      <a href="/reportes" class="btn btn-b">Reportes</a>
      <a href="/agenda" class="btn btn-o">Agenda</a>
      <a href="/seguridad" class="btn btn-r">🔒 Seguridad</a>
      <a href="/configuracion" class="btn btn-o">⚙️ Config</a>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <script>
    const P={json.dumps(periodos)},IM={json.dumps(ingresos_m)},GM={json.dumps(gastos_m)};
    const NM={json.dumps(nat_m)},MM={json.dumps(mai_m)};
    const ML={json.dumps(medios_labels)},MD={json.dumps(medios_data)};
    const GL={json.dumps(gcat_labels)},GD={json.dumps(gcat_data)};
    const CI={json.dumps(cum_ing)},CG={json.dumps(cum_gas)};
    const MC=['#185FA5','#0F6E56','#1D9E75','#E67E22','#7B68EE','#E24B4A','#888780'];
    const gc='rgba(0,0,0,0.06)',tc='rgba(0,0,0,0.42)';
    const fK=v=>'$'+(Math.abs(v)>=1000?(v/1000).toFixed(0)+'k':Math.round(v));
    const fF=v=>'$'+Math.round(v).toLocaleString('es-AR');
    const base={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>' '+ctx.dataset.label+': '+fF(ctx.raw)}}}}}},scales:{{x:{{ticks:{{color:tc,font:{{size:10}}}},grid:{{color:gc}}}},y:{{ticks:{{color:tc,font:{{size:10}},callback:fK}},grid:{{color:gc}}}}}}}};
    new Chart(document.getElementById('ch1'),{{type:'bar',data:{{labels:P,datasets:[{{label:'Cobrado',data:IM,backgroundColor:'#185FA5',borderRadius:4}},{{label:'Gastos',data:GM,backgroundColor:'#E24B4A',borderRadius:4}}]}},options:base}});
    new Chart(document.getElementById('ch2'),{{type:'bar',data:{{labels:P,datasets:[{{label:'Natasha',data:NM,backgroundColor:'#185FA5',borderRadius:3}},{{label:'Maira',data:MM,backgroundColor:'#0F6E56',borderRadius:3}}]}},options:base}});
    new Chart(document.getElementById('ch3'),{{type:'doughnut',data:{{labels:ML,datasets:[{{data:MD,backgroundColor:MC.slice(0,ML.length),borderWidth:2,borderColor:'#fff'}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{{legend:{{display:false}}}}}}}});
    const lg=document.getElementById('leg3');
    ML.forEach((l,i)=>{{lg.innerHTML+=`<span style="display:flex;align-items:center;gap:5px"><span style="width:9px;height:9px;border-radius:2px;background:${{MC[i]}};flex-shrink:0;display:inline-block"></span>${{l}} <b>${{MD[i]}}%</b></span>`}});
    const gDiv=document.getElementById('gcat'),mxG=Math.max(...GD)||1;
    GL.forEach((l,i)=>{{gDiv.innerHTML+=`<div style="display:flex;align-items:center;gap:7px;font-size:.78rem"><span style="width:100px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{l}}</span><div style="flex:1;background:var(--border);border-radius:3px;height:7px"><div style="width:${{Math.round(GD[i]/mxG*100)}}%;height:100%;background:#E67E22;border-radius:3px"></div></div><span style="width:70px;text-align:right;font-weight:600">${{fK(GD[i])}}</span></div>`}});
    new Chart(document.getElementById('ch4'),{{type:'line',data:{{labels:P,datasets:[{{label:'Ingresos',data:CI,borderColor:'#1D9E75',backgroundColor:'rgba(29,158,117,0.07)',fill:true,tension:0.35,pointRadius:3,pointBackgroundColor:'#1D9E75'}},{{label:'Gastos',data:CG,borderColor:'#E24B4A',backgroundColor:'rgba(226,75,74,0.05)',fill:true,tension:0.35,pointRadius:3,pointBackgroundColor:'#E24B4A',borderDash:[5,3]}}]}},options:base}});
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Panel", body, "Panel")

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL DE SEGURIDAD
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/seguridad", methods=["GET","POST"])
@admin_req
def seguridad():
    conn=conectar();c=conn.cursor();flash=""

    if request.method=="POST":
        accion = request.form.get("accion","")
        if accion == "desbloquear_ip":
            ip_d = request.form.get("ip","").strip()
            desbloquear_ip_admin(ip_d)
            c.execute("UPDATE ips_bloqueadas SET desbloqueada=TRUE WHERE ip=%s",(ip_d,))
            conn.commit()
            c.execute("UPDATE seguridad_eventos SET resuelto=TRUE WHERE ip=%s AND tipo='BLOQUEO_IP'",(ip_d,))
            conn.commit()
            flash = f'<div class="flash fok">IP {ip_d} desbloqueada</div>'
            registrar_auditoria("DESBLOQUEO_IP",f"Admin desbloqueó {ip_d}")
        elif accion == "resolver_evento":
            eid = request.form.get("eid","")
            c.execute("UPDATE seguridad_eventos SET resuelto=TRUE WHERE id=%s",(eid,))
            conn.commit()
            flash = '<div class="flash fok">Evento marcado como resuelto</div>'
        elif accion == "bloquear_ip_manual":
            ip_m = request.form.get("ip_manual","").strip()
            motivo = request.form.get("motivo","Bloqueo manual").strip()
            if ip_m:
                LOGIN_INTENTOS[ip_m] = {"count":99,"ts":time.time(),"blocked_until":time.time()+86400*7}
                c.execute("INSERT INTO ips_bloqueadas(ip,motivo,fecha) VALUES(%s,%s,%s) ON CONFLICT(ip) DO UPDATE SET motivo=%s,fecha=%s,desbloqueada=FALSE",
                          (ip_m,motivo,now_ar(),motivo,now_ar()))
                conn.commit()
                registrar_evento_seguridad("BLOQUEO_MANUAL",f"Admin bloqueó {ip_m}: {motivo}",ip_m)
                flash = f'<div class="flash fok">IP {ip_m} bloqueada manualmente</div>'
        elif accion == "enviar_test_wa":
            enviar_whatsapp(f"✅ TEST - Sistema Estudio Carlon funcionando\n📅 {now_ar()}")
            flash = '<div class="flash fok">Mensaje de prueba enviado por WhatsApp</div>'

    # Cargar datos de seguridad
    c.execute("SELECT tipo,detalle,ip,usuario,fecha,id,resuelto FROM seguridad_eventos ORDER BY id DESC LIMIT 100")
    eventos = c.fetchall()
    c.execute("SELECT ip,motivo,fecha,desbloqueada FROM ips_bloqueadas ORDER BY id DESC LIMIT 50")
    ips_bl = c.fetchall()
    c.execute("SELECT COUNT(*) FROM seguridad_eventos WHERE resuelto=FALSE");total_pend = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM seguridad_eventos WHERE tipo='LOGIN_FALLIDO' AND fecha LIKE %s",(f"%{datetime.now().strftime('%d/%m/%Y')}%",));hoy_fallidos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM seguridad_eventos WHERE tipo='BLOQUEO_IP'");total_bloq = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM seguridad_eventos WHERE tipo='LOGIN_OK' AND fecha LIKE %s",(f"%{datetime.now().strftime('%d/%m/%Y')}%",));hoy_ok = c.fetchone()[0]
    conn.close()

    # IPs actualmente bloqueadas en memoria
    ips_mem = [(ip,d) for ip,d in LOGIN_INTENTOS.items() if d.get("blocked_until",0) > time.time()]

    filas_ev = ""
    colores = {"BLOQUEO_IP":"red","ACCESO_PAIS_BLOQUEADO":"red","LOGIN_FALLIDO":"orange","LOGIN_OK":"green","LOGOUT":"green","LOGIN_MANUAL":"orange"}
    for ev in eventos:
        tipo,det,ip_ev,usr_ev,fec,eid,res = ev
        col = colores.get(tipo,"")
        resuelto_badge = '<span class="sec-badge ok">✓</span>' if res else f'<form method="post" style="display:inline"><input type=hidden name=accion value=resolver_evento><input type=hidden name=eid value={eid}><button class="btn btn-xs btn-o">Resolver</button></form>'
        filas_ev += f'<div class="logrow"><div class="log-dot {col}"></div><span class="log-time">{fec}</span><span class="log-user" style="min-width:90px;font-size:.7rem">{tipo}</span><span class="log-msg">{det} {" · "+usr_ev if usr_ev else ""} {" · IP:"+ip_ev if ip_ev else ""}</span>{resuelto_badge}</div>'

    filas_ips = ""
    for ip_b,mot,fec_b,desbl in ips_bl:
        estado = '<span class="sec-badge ok">Desbloqueada</span>' if desbl else '<span class="sec-badge danger">Bloqueada</span>'
        btn_desbl = "" if desbl else f'<form method="post" style="display:inline"><input type=hidden name=accion value=desbloquear_ip><input type=hidden name=ip value="{ip_b}"><button class="btn btn-xs btn-g">Desbloquear</button></form>'
        filas_ips += f'<tr><td class="nm">{ip_b}</td><td class="mu">{mot}</td><td class="mu">{fec_b}</td><td>{estado}</td><td>{btn_desbl}</td></tr>'

    ips_mem_html = ""
    for ip_m,d in ips_mem:
        mins_rest = int((d["blocked_until"] - time.time()) / 60) + 1
        ips_mem_html += f'<div class="logrow"><div class="log-dot red"></div><span class="log-time">Activa</span><span class="log-user">{ip_m}</span><span class="log-msg">{d["count"]} intentos · {mins_rest} min restantes</span><form method="post" style="display:inline"><input type=hidden name=accion value=desbloquear_ip><input type=hidden name=ip value="{ip_m}"><button class="btn btn-xs btn-g">Desbloquear</button></form></div>'

    body = f"""
    <h1 class="page-title">🔒 Panel de Seguridad</h1>
    <p class="page-sub">Monitoreo de accesos, alertas y bloqueos</p>
    {flash}
    <div class="stats">
      <div class="scard r"><div class="sicon">⚠️</div><div class="slabel">Alertas pendientes</div><div class="sval">{total_pend}</div></div>
      <div class="scard o"><div class="sicon">🔴</div><div class="slabel">Fallos hoy</div><div class="sval">{hoy_fallidos}</div></div>
      <div class="scard p"><div class="sicon">🛡️</div><div class="slabel">IPs bloqueadas</div><div class="sval">{total_bloq}</div></div>
      <div class="scard g"><div class="sicon">✅</div><div class="slabel">Logins ok hoy</div><div class="sval">{hoy_ok}</div></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px" class="twocol">
      <div class="fcard" style="margin-bottom:0">
        <h3>🔴 IPs bloqueadas en este momento</h3>
        {ips_mem_html or '<p style="color:var(--muted);font-size:.84rem">Ninguna IP bloqueada</p>'}
      </div>
      <div class="fcard" style="margin-bottom:0">
        <h3>🛡️ Bloquear IP manualmente</h3>
        <form method="post">
          <input type="hidden" name="accion" value="bloquear_ip_manual">
          <div class="fgrid" style="grid-template-columns:1fr">
            <div class="fg"><label>Dirección IP</label><input name="ip_manual" placeholder="192.168.1.100"></div>
            <div class="fg"><label>Motivo</label><input name="motivo" placeholder="Actividad sospechosa" value="Bloqueo manual admin"></div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-r btn-sm">Bloquear IP</button>
            <form method="post" style="display:inline"><input type=hidden name=accion value=enviar_test_wa><button class="btn btn-wa btn-sm">📱 Test WhatsApp</button></form>
          </div>
        </form>
      </div>
    </div>

    <div class="fcard">
      <h3>📋 Historial de IPs bloqueadas</h3>
      <div class="dtable"><table>
        <thead><tr><th>IP</th><th>Motivo</th><th>Fecha</th><th>Estado</th><th>Acción</th></tr></thead>
        <tbody>{filas_ips or "<tr><td colspan=5 style='color:var(--muted);text-align:center;padding:20px'>Sin registros</td></tr>"}</tbody>
      </table></div>
    </div>

    <div class="fcard">
      <h3>🔍 Registro de eventos de seguridad</h3>
      <div class="search"><span>🔍</span><input id="bus" placeholder="Filtrar eventos..." oninput="filtEv(this.value)"></div>
      <div id="ev-lista">
        {filas_ev or '<p style="color:var(--muted);font-size:.84rem">Sin eventos registrados</p>'}
      </div>
    </div>
    <script>
    function filtEv(q){{q=q.toLowerCase();document.querySelectorAll('#ev-lista .logrow').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?'flex':'none')}}
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Seguridad", body, "🔒 Seguridad")

# ══════════════════════════════════════════════════════════════════════════════
#  PANEL DE CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/configuracion", methods=["GET","POST"])
@admin_req
def configuracion():
    conn=conectar();c=conn.cursor();flash=""

    if request.method=="POST":
        accion = request.form.get("accion","")

        if accion == "crear_usuario":
            usuario=request.form.get("usuario","").strip()
            clave=request.form.get("clave","").strip()
            rol=request.form.get("rol","secretaria")
            display=request.form.get("nombre_display","").strip() or usuario
            if not usuario or not clave:
                flash='<div class="flash ferr">Completá usuario y contraseña</div>'
            elif len(clave) < 6:
                flash='<div class="flash ferr">Contraseña mínimo 6 caracteres</div>'
            else:
                c.execute("SELECT id FROM usuarios WHERE usuario=%s",(usuario,))
                if c.fetchone():
                    flash='<div class="flash ferr">Ese usuario ya existe</div>'
                else:
                    c.execute("INSERT INTO usuarios(usuario,clave,rol,nombre_display) VALUES(%s,%s,%s,%s)",
                              (usuario,generate_password_hash(clave),rol,display))
                    conn.commit()
                    registrar_auditoria("NUEVO USUARIO",f"@{usuario} Rol:{rol}")
                    registrar_evento_seguridad("NUEVO_USUARIO",f"Creado @{usuario} rol:{rol}",get_ip())
                    flash=f'<div class="flash fok">✅ Usuario {display} creado correctamente</div>'

        elif accion == "cambiar_clave":
            uid=request.form.get("uid")
            nueva=request.form.get("nueva_clave","").strip()
            confirmar=request.form.get("confirmar_clave","").strip()
            if nueva != confirmar:
                flash='<div class="flash ferr">Las contraseñas no coinciden</div>'
            elif len(nueva) < 6:
                flash='<div class="flash ferr">Mínimo 6 caracteres</div>'
            else:
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s",(generate_password_hash(nueva),uid))
                conn.commit()
                c.execute("SELECT nombre_display,usuario FROM usuarios WHERE id=%s",(uid,))
                u=c.fetchone()
                registrar_auditoria("CAMBIO_CLAVE",f"Clave cambiada para @{u[1] if u else uid}")
                registrar_evento_seguridad("CAMBIO_CLAVE",f"Admin cambió clave de @{u[1] if u else uid}",get_ip())
                flash='<div class="flash fok">✅ Contraseña actualizada</div>'

        elif accion == "cambiar_mis_datos":
            nd2=request.form.get("nuevo_display","").strip()
            nc2=request.form.get("nueva_clave_admin","").strip()
            nc2_conf=request.form.get("confirmar_clave_admin","").strip()
            user_actual=session.get("user")
            if nd2:
                c.execute("UPDATE usuarios SET nombre_display=%s WHERE usuario=%s",(nd2,user_actual))
                session["display"]=nd2
            if nc2:
                if nc2 != nc2_conf:
                    flash='<div class="flash ferr">Las contraseñas no coinciden</div>'
                elif len(nc2) < 6:
                    flash='<div class="flash ferr">Mínimo 6 caracteres</div>'
                else:
                    c.execute("UPDATE usuarios SET clave=%s WHERE usuario=%s",(generate_password_hash(nc2),user_actual))
            conn.commit()
            if not flash:
                flash='<div class="flash fok">✅ Datos actualizados</div>'

        elif accion == "borrar_usuario":
            uid=request.form.get("uid")
            c.execute("SELECT usuario,nombre_display FROM usuarios WHERE id=%s",(uid,))
            u=c.fetchone()
            if u and u[0]!=session.get("user"):
                c.execute("DELETE FROM usuarios WHERE id=%s",(uid,))
                conn.commit()
                registrar_auditoria("BAJA_USUARIO",f"Eliminado @{u[0]}")
                flash='<div class="flash fok">Usuario eliminado</div>'
            else:
                flash='<div class="flash ferr">No podés eliminar tu propio usuario</div>'

        elif accion == "activar_2fa":
            uid = request.form.get("uid")
            c.execute("SELECT usuario,totp_secret FROM usuarios WHERE id=%s",(uid,))
            u = c.fetchone()
            if u:
                secret = u[1] or pyotp.random_base32()
                c.execute("UPDATE usuarios SET totp_secret=%s,totp_habilitado=TRUE WHERE id=%s",(secret,uid))
                conn.commit()
                flash=f'<div class="flash fok">✅ 2FA activado para @{u[0]}</div>'

        elif accion == "desactivar_2fa":
            uid = request.form.get("uid")
            c.execute("UPDATE usuarios SET totp_habilitado=FALSE WHERE id=%s",(uid,))
            conn.commit()
            flash='<div class="flash fok">2FA desactivado</div>'

        elif accion == "guardar_config_seg":
            keys = ["max_intentos_login","bloqueo_mins","paises_permitidos","alerta_whatsapp","session_timeout_mins"]
            for k in keys:
                v = request.form.get(k,"")
                if v:
                    c.execute("UPDATE config_seguridad SET valor=%s WHERE clave=%s",(v,k))
            conn.commit()
            flash='<div class="flash fok">✅ Configuración de seguridad guardada</div>'

        elif accion == "activar_desactivar_usuario":
            uid = request.form.get("uid")
            activo_val = request.form.get("activo_val","1")
            c.execute("UPDATE usuarios SET activo=%s WHERE id=%s",(activo_val=="1",uid))
            conn.commit()
            flash='<div class="flash fok">Estado de usuario actualizado</div>'

    # Cargar datos
    c.execute("SELECT id,usuario,rol,nombre_display,totp_habilitado,activo FROM usuarios ORDER BY rol,usuario")
    lista = c.fetchall()
    c.execute("SELECT clave,valor FROM config_seguridad")
    config = {r[0]:r[1] for r in c.fetchall()}
    conn.close()

    # Generar QR codes para 2FA por usuario
    qr_html = ""
    cards = ""
    for u in lista:
        uid,uname,urol,udisp,totp_on,activo = u
        badge = '<span class="badge badm">Admin</span>' if urol=="admin" else '<span class="badge bsec">Secretaria</span>'
        activo_badge = '<span class="sec-badge ok">Activo</span>' if activo else '<span class="sec-badge danger">Inactivo</span>'
        totp_badge = '<span class="sec-badge ok">2FA ✓</span>' if totp_on else '<span class="sec-badge warn">2FA off</span>'
        es_yo = uname == session.get("user")

        btn_del = '<span style="font-size:.73rem;color:var(--muted)">sos vos</span>' if es_yo else \
            f'<form method="post" style="display:inline" onsubmit="return confirm(\'Eliminar a {udisp or uname}?\')"><input type=hidden name=accion value=borrar_usuario><input type=hidden name=uid value={uid}><button class="btn btn-xs btn-r">🗑</button></form>'

        btn_2fa = f'<form method="post" style="display:inline"><input type=hidden name=accion value={"desactivar_2fa" if totp_on else "activar_2fa"}><input type=hidden name=uid value={uid}><button class="btn btn-xs {"btn-o" if totp_on else "btn-b"}">{"Desact. 2FA" if totp_on else "Activar 2FA"}</button></form>'

        btn_act = f'<form method="post" style="display:inline"><input type=hidden name=accion value=activar_desactivar_usuario><input type=hidden name=uid value={uid}><input type=hidden name=activo_val value={"0" if activo else "1"}><button class="btn btn-xs {"btn-o" if activo else "btn-g"}">{"Deshabilitar" if activo else "Habilitar"}</button></form>' if not es_yo else ""

        cards += f'''<div class="ucard {"adm" if urol=="admin" else ""}">
          <div>
            <div style="font-weight:600;font-size:.96rem;color:var(--primary)">{udisp or uname} {badge}</div>
            <div style="font-size:.75rem;color:var(--muted)">@{uname}</div>
            <div style="margin-top:4px;display:flex;gap:5px">{activo_badge}{totp_badge}</div>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
            <button onclick="abrirClave({uid},'{uname}')" class="btn btn-xs btn-o">🔑 Clave</button>
            {btn_2fa}{btn_act}{btn_del}
          </div>
        </div>'''

    body = f"""
    <h1 class="page-title">⚙️ Configuración</h1>
    <p class="page-sub">Usuarios, contraseñas, seguridad y 2FA</p>
    {flash}

    <div class="tabs">
      <button class="tab on" onclick="showTab('t1',this)">👥 Usuarios</button>
      <button class="tab" onclick="showTab('t2',this)">➕ Nuevo Usuario</button>
      <button class="tab" onclick="showTab('t3',this)">🔒 Mi Cuenta</button>
      <button class="tab" onclick="showTab('t4',this)">🛡️ Config. Seguridad</button>
    </div>

    <div id="t1" class="tabpanel on">
      <div class="fcard">
        <h3>Usuarios del sistema ({len(lista)})</h3>
        {cards or '<p style="color:var(--muted)">Sin usuarios</p>'}
      </div>
      <div class="fcard">
        <h3>ℹ️ Permisos por rol</h3>
        <div class="info-box" style="margin-bottom:8px"><b>Admin:</b> Panel financiero, gráficos, reportes, usuarios, configuración, seguridad, todos los módulos.</div>
        <div style="background:#f0f4ff;border:1px solid #b0c4ee;border-radius:8px;padding:10px 14px;font-size:.8rem;color:#1a3a8a"><b>Secretaria:</b> Clientes, pagos, recibos, gastos, caja, agenda. Sin acceso a panel, reportes, usuarios ni configuración.</div>
      </div>
    </div>

    <div id="t2" class="tabpanel">
      <div class="fcard">
        <h3>➕ Crear nuevo usuario</h3>
        <form method="post">
          <input type="hidden" name="accion" value="crear_usuario">
          <div class="fgrid">
            <div class="fg"><label>Nombre completo</label><input name="nombre_display" placeholder="María González"></div>
            <div class="fg"><label>Usuario (login)</label><input name="usuario" placeholder="mariag" required></div>
            <div class="fg"><label>Contraseña</label><input name="clave" type="password" placeholder="Mínimo 6 caracteres" required></div>
            <div class="fg"><label>Rol</label>
              <select name="rol">
                <option value="secretaria">Secretaria</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
          </div>
          <div class="info-box">🔒 Las contraseñas se guardan encriptadas con hash seguro (bcrypt). Nunca se almacenan en texto plano.</div>
          <button class="btn btn-p">Crear Usuario</button>
        </form>
      </div>
    </div>

    <div id="t3" class="tabpanel">
      <div class="fcard">
        <h3>🔒 Mis datos — {session.get("display","")}</h3>
        <form method="post">
          <input type="hidden" name="accion" value="cambiar_mis_datos">
          <div class="fgrid">
            <div class="fg"><label>Nombre para mostrar</label><input name="nuevo_display" value="{session.get('display','')}"></div>
            <div class="fg"><label>Nueva contraseña (vacío = no cambia)</label><input name="nueva_clave_admin" type="password" placeholder="Nueva contraseña"></div>
            <div class="fg"><label>Confirmar nueva contraseña</label><input name="confirmar_clave_admin" type="password" placeholder="Repetir contraseña"></div>
          </div>
          <button class="btn btn-a btn-sm">Guardar mis datos</button>
        </form>
      </div>
    </div>

    <div id="t4" class="tabpanel">
      <div class="fcard">
        <h3>🛡️ Configuración de seguridad</h3>
        <form method="post">
          <input type="hidden" name="accion" value="guardar_config_seg">
          <div class="fgrid">
            <div class="fg">
              <label>Intentos máx. login antes de bloquear</label>
              <input name="max_intentos_login" type="number" value="{config.get('max_intentos_login','5')}" min="2" max="20">
            </div>
            <div class="fg">
              <label>Minutos de bloqueo por IP</label>
              <input name="bloqueo_mins" type="number" value="{config.get('bloqueo_mins','30')}" min="5" max="1440">
            </div>
            <div class="fg">
              <label>Países permitidos (cod. ISO, ej: AR)</label>
              <input name="paises_permitidos" value="{config.get('paises_permitidos','AR')}" placeholder="AR,UY,CL">
            </div>
            <div class="fg">
              <label>Timeout de sesión (minutos)</label>
              <input name="session_timeout_mins" type="number" value="{config.get('session_timeout_mins','120')}" min="15" max="480">
            </div>
            <div class="fg">
              <label>Alertas WhatsApp</label>
              <select name="alerta_whatsapp">
                <option value="1" {"selected" if config.get('alerta_whatsapp','1')=='1' else ""}>Habilitadas</option>
                <option value="0" {"selected" if config.get('alerta_whatsapp','1')=='0' else ""}>Deshabilitadas</option>
              </select>
            </div>
          </div>
          <div class="info-box" style="margin-bottom:14px">
            📱 Alertas WhatsApp al número <b>{WHATSAPP_NUMERO}</b> via CallMeBot.<br>
            🌎 Bloqueo por país usando ip-api.com.<br>
            🔐 Datos sensibles (CUIT, teléfono, email) encriptados con Fernet AES-128.<br>
            🤖 Rate limiting activo: anti-bots automático.
          </div>
          <button class="btn btn-p">Guardar configuración</button>
        </form>
      </div>

      <div class="fcard">
        <h3>🔐 Google Authenticator (2FA)</h3>
        <div class="info-box" style="margin-bottom:14px">
          Para activar el 2FA en un usuario:<br>
          1. Hacé clic en "Activar 2FA" en la lista de usuarios (pestaña Usuarios)<br>
          2. El usuario debe abrir Google Authenticator → Agregar cuenta → Escanear QR<br>
          3. Ve a <a href="/configuracion/qr_2fa?uid=ID" style="color:var(--primary)">Ver QR de usuario</a> para obtener el código QR
        </div>
        <a href="/configuracion/mi_2fa" class="btn btn-b">Ver mi QR de 2FA</a>
      </div>
    </div>

    <div class="mo" id="mc"><div class="modal">
      <h3>🔑 Cambiar Contraseña</h3><p class="msub" id="mc-sub"></p>
      <form method="post">
        <input type="hidden" name="accion" value="cambiar_clave">
        <input type="hidden" name="uid" id="mc-uid">
        <div class="fg" style="margin-bottom:12px"><label>Nueva contraseña</label><input name="nueva_clave" type="password" placeholder="Mínimo 6 caracteres" required></div>
        <div class="fg" style="margin-bottom:14px"><label>Confirmar contraseña</label><input name="confirmar_clave" type="password" placeholder="Repetir contraseña" required></div>
        <div class="mact"><button type="button" class="btn btn-o" onclick="closeM('mc')">Cancelar</button><button type="submit" class="btn btn-p">Guardar</button></div>
      </form>
    </div></div>

    <script>
    function showTab(id,btn){{document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));document.getElementById(id).classList.add('on');btn.classList.add('on')}}
    function abrirClave(id,u){{document.getElementById('mc-sub').textContent='@'+u;document.getElementById('mc-uid').value=id;document.getElementById('mc').classList.add('on')}}
    function closeM(id){{document.getElementById(id).classList.remove('on')}}
    document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}))
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Configuración", body, "⚙️ Config")

@app.route("/configuracion/mi_2fa")
@login_req
def mi_2fa():
    conn=conectar();c=conn.cursor()
    c.execute("SELECT totp_secret,totp_habilitado FROM usuarios WHERE usuario=%s",(session.get("user"),))
    row=c.fetchone();conn.close()
    secret = row[0] if row else None
    habilitado = row[1] if row else False
    if not secret:
        # Generar y guardar secret
        secret = pyotp.random_base32()
        conn=conectar();c=conn.cursor()
        c.execute("UPDATE usuarios SET totp_secret=%s WHERE usuario=%s",(secret,session.get("user")))
        conn.commit();conn.close()
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=session.get("user","usuario"),
        issuer_name="Estudio Carlon"
    )
    qr=qrcode.make(totp_uri)
    qb=BytesIO();qr.save(qb);qb.seek(0)
    import base64 as b64
    qr_b64 = b64.b64encode(qb.read()).decode()
    estado_badge = '<span class="sec-badge ok">2FA ACTIVO ✓</span>' if habilitado else '<span class="sec-badge warn">2FA no activado aún</span>'
    body = f"""
    <h1 class="page-title">🔐 Mi Google Authenticator</h1>
    <p class="page-sub">Configuración del segundo factor de autenticación</p>
    <div class="fcard" style="max-width:500px">
      <h3>Escanear código QR</h3>
      {estado_badge}
      <div style="margin:20px 0;text-align:center">
        <img src="data:image/png;base64,{qr_b64}" style="border:8px solid #fff;border-radius:8px;box-shadow:var(--shadow);max-width:200px">
      </div>
      <div class="info-box">
        <b>Pasos:</b><br>
        1. Instalá Google Authenticator en tu celular<br>
        2. Tocá el + → "Escanear código QR"<br>
        3. Apuntá la cámara al QR de arriba<br>
        4. Se va a agregar "Estudio Carlon - {session.get("user","")}"<br>
        5. El código cambia cada 30 segundos
      </div>
      <div style="background:#f5f3ff;border:1px solid #c4b5f7;border-radius:8px;padding:10px 14px;font-size:.82rem;margin-top:12px">
        <b>Clave manual:</b> <code style="font-size:.9rem;letter-spacing:2px">{secret}</code><br>
        <span style="color:var(--muted);font-size:.74rem">Usá esto si no podés escanear el QR</span>
      </div>
      <div style="margin-top:16px">
        <a href="/configuracion" class="btn btn-p">← Volver a configuración</a>
      </div>
    </div>"""
    return page("Mi 2FA", body)

# ══════════════════════════════════════════════════════════════════════════════
#  ASISTENTE IA
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/asistente", methods=["POST"])
@login_req
def asistente():
    try:
        data = request.get_json()
        mensajes = data.get("mensajes", [])
        if not ANTHROPIC_API_KEY: return jsonify({"respuesta": None})
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 400,
            "system": "Sos el asistente del Estudio Contable Carlon de Santiago del Estero, Argentina. Respondé preguntas sobre el sistema, contabilidad e impuestos en español. Sé conciso.",
            "messages": mensajes[-8:]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        return jsonify({"respuesta": result["content"][0]["text"]})
    except:
        return jsonify({"respuesta": None})

# ══════════════════════════════════════════════════════════════════════════════
#  CLIENTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/clientes", methods=["GET","POST"])
@login_req
def clientes():
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        nombre=request.form.get("nombre","").strip();cuit=request.form.get("cuit","").strip()
        tel=request.form.get("telefono","").strip();email=request.form.get("email","").strip()
        abono=request.form.get("abono",0) or 0
        # Encriptar datos sensibles
        c.execute("INSERT INTO clientes(nombre,cuit,telefono,email,abono) VALUES(%s,%s,%s,%s,%s)",
                  (nombre,enc(cuit),enc(tel),enc(email),abono))
        conn.commit()
        periodo=datetime.now().strftime("%m/%Y")
        c.execute("SELECT id FROM clientes WHERE nombre=%s ORDER BY id DESC LIMIT 1",(nombre,))
        row=c.fetchone()
        if row:
            c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,%s,0)",(row[0],periodo,float(abono) if abono else 0))
            conn.commit();registrar_auditoria("NUEVO CLIENTE",f"CUIT:{cuit} Hon:{fmt(abono)}",row[0],nombre)
        flash=f'<div class="flash fok">Cliente {nombre} agregado</div>'
    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes ORDER BY nombre")
    data_raw=c.fetchall();conn.close();es_admin=session.get("rol")=="admin"
    rows=""
    for d in data_raw:
        cid,nombre,cuit_enc,tel_enc,email_enc,abono=d
        cuit_d=dec(cuit_enc);tel_d=dec(tel_enc);email_d=dec(email_enc)
        btn_del=f'<button onclick="confBorrar({cid},\'{nombre.replace(chr(39),"")}\',event)" class="btn btn-xs btn-r">🗑</button>' if es_admin else ""
        rows+=f'<tr data-search="{nombre.lower()} {(cuit_d or "").lower()} {(email_d or "").lower()}"><td class="nm">{nombre}</td><td class="mu">{cuit_d or "---"}</td><td class="mu">{tel_d or "---"}</td><td class="mu">{email_d or "---"}</td><td>{fmt(abono or 0)}</td><td style="white-space:nowrap;display:flex;gap:5px;flex-wrap:wrap"><a href="/cuenta/{cid}" class="btn btn-xs btn-p">Cuenta</a><a href="/editar_cliente/{cid}" class="btn btn-xs btn-o">Editar</a>{btn_del}</td></tr>'
    modal='<div class="mo" id="mb"><div class="modal"><h3>Eliminar cliente?</h3><p class="msub" id="mb-nm"></p><p style="font-size:.81rem;color:var(--muted)">Se eliminan todos sus registros.</p><div class="mact"><button class="btn btn-o" onclick="closeM(\'mb\')">Cancelar</button><a id="mb-ok" href="#" class="btn btn-r">Eliminar</a></div></div></div>' if es_admin else ""
    body=f"""
    <h1 class="page-title">Clientes</h1><p class="page-sub">{len(data_raw)} clientes registrados</p>{flash}
    <div class="fcard"><h3>Nuevo Cliente</h3><form method="post">
      <div class="fgrid">
        <div class="fg"><label>Nombre / Razón Social</label><input name="nombre" required placeholder="Garcia Juan"></div>
        <div class="fg"><label>CUIT</label><input name="cuit" placeholder="20-12345678-9"></div>
        <div class="fg"><label>Teléfono</label><input name="telefono" placeholder="3846000000"></div>
        <div class="fg"><label>Email</label><input name="email" type="email" placeholder="cliente@email.com"></div>
        <div class="fg"><label>Honorarios $ / mes</label><input name="abono" type="number" placeholder="0"></div>
      </div>
      <div class="info-box" style="margin-bottom:10px">🔒 CUIT, teléfono y email se guardan encriptados en la base de datos.</div>
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

@app.route("/editar_cliente/<int:id>", methods=["GET","POST"])
@login_req
def editar_cliente(id):
    conn=conectar();c=conn.cursor()
    if request.method=="POST":
        c.execute("SELECT nombre,cuit,telefono,email,abono FROM clientes WHERE id=%s",(id,))
        antes=c.fetchone()
        nombre=request.form.get("nombre","").strip();cuit=request.form.get("cuit","").strip()
        tel=request.form.get("telefono","").strip();email=request.form.get("email","").strip();abono=request.form.get("abono",0) or 0
        c.execute("UPDATE clientes SET nombre=%s,cuit=%s,telefono=%s,email=%s,abono=%s WHERE id=%s",
                  (nombre,enc(cuit),enc(tel),enc(email),abono,id))
        conn.commit()
        registrar_auditoria("EDICION CLIENTE",f"Actualizado {nombre}",id,nombre)
        conn.close();return redirect("/clientes")
    c.execute("SELECT id,nombre,cuit,telefono,email,abono FROM clientes WHERE id=%s",(id,))
    d=c.fetchone();conn.close()
    cuit_d=dec(d[2]);tel_d=dec(d[3]);email_d=dec(d[4])
    body=f'<a href="/clientes" class="btn btn-o btn-sm" style="margin-bottom:18px">← Volver</a><h1 class="page-title">Editar Cliente</h1><p class="page-sub">{d[1]}</p><div class="fcard"><form method="post"><div class="fgrid"><div class="fg"><label>Nombre</label><input name="nombre" value="{d[1] or ""}" required></div><div class="fg"><label>CUIT</label><input name="cuit" value="{cuit_d or ""}"></div><div class="fg"><label>Teléfono</label><input name="telefono" value="{tel_d or ""}"></div><div class="fg"><label>Email</label><input name="email" type="email" value="{email_d or ""}"></div><div class="fg"><label>Honorarios $</label><input name="abono" type="number" value="{d[5] or 0}"></div></div><div style="display:flex;gap:8px"><button class="btn btn-p">Guardar</button><a href="/clientes" class="btn btn-o">Cancelar</a></div></form></div>'
    return page(f"Editar - {d[1]}",body,"Clientes")

@app.route("/borrar_cliente/<int:id>")
@admin_req
def borrar_cliente(id):
    conn=conectar();c=conn.cursor()
    c.execute("SELECT nombre FROM clientes WHERE id=%s",(id,));row=c.fetchone();nombre=row[0] if row else "?"
    c.execute("DELETE FROM cuentas WHERE cliente_id=%s",(id,));c.execute("DELETE FROM pagos WHERE cliente_id=%s",(id,));c.execute("DELETE FROM clientes WHERE id=%s",(id,))
    conn.commit();conn.close();registrar_auditoria("BAJA CLIENTE","Cliente eliminado",id,nombre);return redirect("/clientes")

# ══════════════════════════════════════════════════════════════════════════════
#  CUENTA / PAGOS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/cuenta/<int:id>", methods=["GET","POST"])
@login_req
def cuenta(id):
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        periodo=request.form.get("periodo","").strip();pago=float(request.form.get("pago",0) or 0)
        medio=request.form.get("medio","Efectivo");obs=request.form.get("observaciones","").strip()
        facturado=request.form.get("facturado","0")=="1"
        c.execute("SELECT id,haber FROM cuentas WHERE cliente_id=%s AND periodo=%s",(id,periodo))
        row=c.fetchone()
        if row: c.execute("UPDATE cuentas SET haber=COALESCE(haber,0)+%s WHERE cliente_id=%s AND periodo=%s",(pago,id,periodo))
        else: c.execute("INSERT INTO cuentas(cliente_id,periodo,debe,haber) VALUES(%s,%s,0,%s)",(id,periodo,pago))
        conn.commit()
        c.execute("SELECT nombre FROM clientes WHERE id=%s",(id,));nom=c.fetchone();nombre_cli=nom[0] if nom else "?"
        c.execute("INSERT INTO pagos(cliente_id,periodo,monto,medio,observaciones,facturado,fecha,usuario,emitido_por) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (id,periodo,pago,medio,obs,facturado,now_ar(),session.get("display",""),session.get("display","")))
        conn.commit()
        registrar_auditoria("PAGO REGISTRADO",f"Periodo:{periodo} | Monto:{fmt(pago)} | Medio:{medio}",id,nombre_cli)
        flash=f'<div class="flash fok">Pago de {fmt(pago)} registrado - {medio}</div>'
    c.execute("SELECT nombre,cuit,telefono,email FROM clientes WHERE id=%s",(id,))
    cli=c.fetchone()
    if not cli: return "Cliente no encontrado",404
    nombre,cuit_enc,tel_enc,email_enc=cli
    cuit=dec(cuit_enc);tel=dec(tel_enc);email=dec(email_enc)
    c.execute("SELECT periodo,debe,haber FROM cuentas WHERE cliente_id=%s ORDER BY SUBSTRING(periodo,4,4) DESC,SUBSTRING(periodo,1,2) DESC",(id,))
    datos=c.fetchall()
    c.execute("SELECT fecha,usuario,periodo,monto,medio,facturado,observaciones,emitido_por FROM pagos WHERE cliente_id=%s ORDER BY id DESC LIMIT 30",(id,))
    historial=c.fetchall();conn.close()
    total_deuda=sum(max(d[1]-d[2],0) for d in datos);total_pago=sum(d[2] for d in datos)
    filas=""
    for d in datos:
        saldo=d[1]-d[2]
        if saldo<=0: badge='<span class="badge bp">PAGADO</span>'
        elif d[2]>0: badge=f'<span class="badge bpar">PARCIAL - debe {fmt(saldo)}</span>'
        else: badge=f'<span class="badge bd">DEBE {fmt(saldo)}</span>'
        telefono=(tel or "").replace(" ","").replace("+","").strip()
        wa_msg=f"Hola {nombre}, tiene deuda de {fmt(saldo)} del periodo {d[0]}. Transferir al CBU 0110420630042013452529 Alias: ESTUDIO.CONTA.CARLON"
        wa_link=f"https://wa.me/{telefono}?text={wa_msg.replace(' ','%20')}" if telefono else "#"
        pu=d[0].replace("/","-")
        btn_p=f'<button onclick="abrirPago(\'{d[0]}\',{saldo})" class="btn btn-xs btn-g">Pagar</button>' if saldo>0 else '<span style="color:var(--success);font-size:.73rem;font-weight:600">Al dia</span>'
        filas+=f'<div class="arow"><span class="period">{d[0]}</span><span style="font-size:.86rem">{fmt(d[2] if d[2]>0 else d[1])}</span>{badge}<div style="display:flex;gap:5px;flex-wrap:wrap"><a href="/recibo/{id}/{pu}" target="_blank" class="btn btn-xs btn-o">Ver</a><a href="/recibo/{id}/{pu}?download=1" class="btn btn-xs btn-o">PDF</a>{btn_p}<a href="https://afip.gob.ar/facturacion/" target="_blank" class="btn btn-xs btn-arca">ARCA</a>{"<a href="+chr(39)+wa_link+chr(39)+" target=_blank class=btn btn-xs btn-wa>WA</a>" if telefono else ""}</div></div>'
    hist_rows=""
    for h in historial:
        fact_b='<span style="color:var(--success);font-size:.69rem;font-weight:700">Facturado</span>' if h[5] else '<span style="color:var(--muted);font-size:.69rem">Sin factura</span>'
        emitido=h[7] or h[1]
        hist_rows+=f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{h[0]}</span><span class="log-user">{emitido}</span><span class="log-msg">{h[2]} · {fmt(h[3])} · {h[4]}{" · "+h[6] if h[6] else ""} {fact_b}</span></div>'
    medios_opts="".join(f'<option value="{m}">{m}</option>' for m in MEDIOS_PAGO)
    body=f"""
    <a href="/clientes" class="btn btn-o btn-sm" style="margin-bottom:18px">← Clientes</a>
    <h1 class="page-title">{nombre}</h1>
    <p class="page-sub">CUIT: {cuit or "---"} · Tel: {tel or "---"} · {email or "---"}</p>
    <div class="stats" style="margin-bottom:16px">
      <div class="scard g"><div class="slabel">Total Cobrado</div><div class="sval">{fmt(total_pago)}</div></div>
      <div class="scard r"><div class="slabel">Deuda Pendiente</div><div class="sval">{fmt(total_deuda)}</div></div>
    </div>
    {flash}
    <div style="display:grid;grid-template-columns:1fr 340px;gap:16px;align-items:start" class="twocol">
      <div>{filas}</div>
      <div>
        <div class="fcard">
          <h3>Registrar Pago</h3>
          <form method="post">
            <div class="fgrid" style="grid-template-columns:1fr">
              <div class="fg"><label>Periodo (MM/AAAA)</label><input name="periodo" value="{datetime.now().strftime('%m/%Y')}" required></div>
              <div class="fg"><label>Monto $</label><input name="pago" type="number" step="0.01" required></div>
              <div class="fg"><label>Medio de pago</label><select name="medio">{medios_opts}</select></div>
              <div class="fg"><label>Observaciones</label><input name="observaciones" placeholder="Opcional"></div>
              <div class="fg" style="flex-direction:row;align-items:center;gap:8px"><input type="checkbox" name="facturado" value="1" style="width:auto"> <label style="text-transform:none;font-size:.84rem">Emitir factura ARCA</label></div>
            </div>
            <button class="btn btn-g">Registrar Pago</button>
          </form>
        </div>
        <div class="fcard"><h3>Historial</h3>{hist_rows or '<p style="color:var(--muted);font-size:.84rem">Sin pagos</p>'}</div>
      </div>
    </div>
    <div class="mo" id="mp"><div class="modal"><h3>Registrar Pago</h3><p class="msub" id="mp-sub"></p>
      <form method="post">
        <input type="hidden" name="periodo" id="mp-per">
        <div class="fg" style="margin-bottom:12px"><label>Monto</label><input name="pago" id="mp-monto" type="number" step="0.01"></div>
        <div class="fg" style="margin-bottom:14px"><label>Medio</label><select name="medio">{medios_opts}</select></div>
        <div class="mact"><button type="button" class="btn btn-o" onclick="closeM('mp')">Cancelar</button><button type="submit" class="btn btn-g">Pagar</button></div>
      </form>
    </div></div>
    <script>
    function abrirPago(p,s){{document.getElementById('mp-sub').textContent=p+' · Saldo: $'+Math.round(s).toLocaleString('es-AR');document.getElementById('mp-per').value=p;document.getElementById('mp-monto').value=Math.round(s);document.getElementById('mp').classList.add('on')}}
    function closeM(id){{document.getElementById(id).classList.remove('on')}}
    document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}))
    </script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page(f"Cuenta - {nombre}", body, "Clientes")

# ══════════════════════════════════════════════════════════════════════════════
#  DEUDAS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/deudas")
@login_req
def deudas():
    conn=conectar();c=conn.cursor()
    c.execute("""SELECT cl.id,cl.nombre,cl.telefono,SUM(cu.debe-cu.haber) saldo
                 FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id
                 GROUP BY cl.id,cl.nombre,cl.telefono
                 HAVING SUM(cu.debe-cu.haber)>0
                 ORDER BY saldo DESC""")
    data=c.fetchall();conn.close()
    total=sum(r[3] for r in data)
    cards=""
    for d in data:
        cid,nombre,tel_enc,saldo=d
        tel_d=dec(tel_enc)
        telefono=(tel_d or "").replace(" ","").replace("+","").strip()
        wa_msg=f"Hola {nombre}, le recordamos que tiene una deuda pendiente de {fmt(saldo)} con el Estudio Contable Carlon. Por favor regularizar. Gracias."
        wa_link=f"https://wa.me/{telefono}?text={wa_msg.replace(' ','%20')}" if telefono else "#"
        cards+=f'<div class="dcard"><div><span class="dname">{nombre}</span></div><div class="damt">{fmt(saldo)}</div><div style="display:flex;gap:6px"><a href="/cuenta/{cid}" class="btn btn-xs btn-p">Ver cuenta</a>{"<a href="+chr(39)+wa_link+chr(39)+" target=_blank class=btn btn-xs btn-wa>📱 WA</a>" if telefono else ""}</div></div>'
    body=f"""
    <h1 class="page-title">Deudores</h1><p class="page-sub">{len(data)} clientes con saldo pendiente · Total: {fmt(total)}</p>
    {cards or '<div class="info-box">Sin deudores 🎉</div>'}"""
    return page("Deudores",body,"Deudores")

# ══════════════════════════════════════════════════════════════════════════════
#  GASTOS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/gastos", methods=["GET","POST"])
@login_req
def gastos():
    conn=conectar();c=conn.cursor();flash=""
    if request.method=="POST":
        fecha=request.form.get("fecha",now_ar());cat=request.form.get("categoria","Otros")
        desc=request.form.get("descripcion","").strip();monto=float(request.form.get("monto",0) or 0)
        c.execute("INSERT INTO gastos(fecha,categoria,descripcion,monto,usuario) VALUES(%s,%s,%s,%s,%s)",
                  (fecha,cat,desc,monto,session.get("display","")))
        conn.commit();registrar_auditoria("GASTO",f"{cat}: {fmt(monto)} - {desc}")
        flash=f'<div class="flash fok">Gasto registrado: {fmt(monto)}</div>'
    c.execute("SELECT id,fecha,categoria,descripcion,monto,usuario FROM gastos ORDER BY id DESC LIMIT 80")
    data=c.fetchall();conn.close()
    total=sum(d[4] for d in data)
    opts="".join(f'<option value="{c}">{c}</option>' for c in CATEGORIAS_GASTO)
    rows="".join(f'<tr><td class="mu">{d[1]}</td><td><span class="bmedio">{d[2]}</span></td><td>{d[3]}</td><td style="font-weight:600;color:var(--danger)">{fmt(d[4])}</td><td class="mu">{d[5]}</td></tr>' for d in data)
    body=f"""
    <h1 class="page-title">Gastos</h1><p class="page-sub">Total registrado: {fmt(total)}</p>{flash}
    <div class="fcard"><h3>Nuevo Gasto</h3><form method="post">
      <div class="fgrid">
        <div class="fg"><label>Fecha</label><input name="fecha" value="{now_ar()}"></div>
        <div class="fg"><label>Categoría</label><select name="categoria">{opts}</select></div>
        <div class="fg"><label>Descripción</label><input name="descripcion" placeholder="Detalle..."></div>
        <div class="fg"><label>Monto $</label><input name="monto" type="number" step="0.01" required></div>
      </div>
      <button class="btn btn-r">Registrar Gasto</button>
    </form></div>
    <div class="dtable"><table>
      <thead><tr><th>Fecha</th><th>Categoría</th><th>Descripción</th><th>Monto</th><th>Usuario</th></tr></thead>
      <tbody>{rows or "<tr><td colspan=5 style='color:var(--muted);text-align:center;padding:20px'>Sin gastos</td></tr>"}</tbody>
    </table></div>"""
    return page("Gastos",body,"Gastos")

# ══════════════════════════════════════════════════════════════════════════════
#  CAJA
# ══════════════════════════════════════════════════════════════════════════════
MEDIOS_FISICOS = ["Efectivo","Cheque","Dólares"]

def _totales_caja(fecha_hoy, usuario):
    conn=conectar();c=conn.cursor()
    c.execute("SELECT medio,SUM(monto) FROM pagos WHERE fecha LIKE %s AND emitido_por=%s GROUP BY medio",
              (f"%{fecha_hoy}%",usuario))
    filas=c.fetchall();conn.close()
    totales={"Efectivo":0,"Cheque":0,"Dólares":0,"Transferencia → Natasha Carlon":0,"Transferencia → Maira Carlon":0,"Otro":0}
    for medio,monto in filas:
        for k in totales:
            if k.lower() in (medio or "").lower():
                totales[k]+=monto or 0;break
        else: totales["Otro"]+=monto or 0
    totales["total_fisico"]=totales["Efectivo"]+totales["Cheque"]+totales["Dólares"]
    totales["total_general"]=sum(v for k,v in totales.items() if k not in ("total_fisico","total_general"))
    return totales

@app.route("/caja", methods=["GET","POST"])
@login_req
def caja():
    conn=conectar();c=conn.cursor();flash=""
    usuario=session.get("display","");rol=session.get("rol","secretaria")
    fecha_hoy=datetime.now().strftime("%d/%m/%Y")
    if request.method=="POST":
        accion=request.form.get("accion","")
        if accion=="cerrar_caja":
            c.execute("SELECT id FROM cierres_caja WHERE fecha=%s AND usuario=%s AND cerrado=TRUE",(fecha_hoy,usuario))
            if c.fetchone(): flash='<div class="flash ferr">Ya cerraste tu caja hoy</div>'
            else:
                tot=_totales_caja(fecha_hoy,usuario)
                c.execute("SELECT p.fecha,cl.nombre,p.monto,p.medio,p.observaciones FROM pagos p JOIN clientes cl ON cl.id=p.cliente_id WHERE p.fecha LIKE %s AND p.emitido_por=%s ORDER BY p.id",
                          (f"%{fecha_hoy}%",usuario))
                pagos_dia=c.fetchall()
                detalle=" | ".join(f"{p[1]}:{fmt(p[2])}({p[3]})" for p in pagos_dia)
                c.execute("SELECT id FROM cierres_caja WHERE fecha=%s AND usuario=%s",(fecha_hoy,usuario))
                existe=c.fetchone()
                if existe:
                    c.execute("UPDATE cierres_caja SET efectivo=%s,cheque=%s,dolares=%s,transferencia_nat=%s,transferencia_mai=%s,otro=%s,total_fisico=%s,total_general=%s,detalle_pagos=%s,cerrado=TRUE,hora_cierre=%s WHERE id=%s",
                              (tot["Efectivo"],tot["Cheque"],tot["Dólares"],tot["Transferencia → Natasha Carlon"],tot["Transferencia → Maira Carlon"],tot["Otro"],tot["total_fisico"],tot["total_general"],detalle,datetime.now().strftime("%H:%M"),existe[0]))
                else:
                    c.execute("INSERT INTO cierres_caja(fecha,usuario,efectivo,cheque,dolares,transferencia_nat,transferencia_mai,otro,total_fisico,total_general,detalle_pagos,cerrado,hora_cierre) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)",
                              (fecha_hoy,usuario,tot["Efectivo"],tot["Cheque"],tot["Dólares"],tot["Transferencia → Natasha Carlon"],tot["Transferencia → Maira Carlon"],tot["Otro"],tot["total_fisico"],tot["total_general"],detalle,datetime.now().strftime("%H:%M")))
                conn.commit()
                registrar_auditoria("CIERRE_CAJA",f"Total: {fmt(tot['total_general'])} | Fisico: {fmt(tot['total_fisico'])}")
                flash=f'<div class="flash fok">Caja cerrada · Total: {fmt(tot["total_general"])}</div>'
    tot_hoy=_totales_caja(fecha_hoy,usuario)
    c.execute("SELECT id FROM cierres_caja WHERE fecha=%s AND usuario=%s AND cerrado=TRUE",(fecha_hoy,usuario))
    ya_cerro=bool(c.fetchone())
    if rol=="admin":
        c.execute("SELECT fecha,usuario,efectivo,cheque,dolares,transferencia_nat,transferencia_mai,otro,total_fisico,total_general,cerrado,hora_cierre FROM cierres_caja ORDER BY id DESC LIMIT 30")
    else:
        c.execute("SELECT fecha,usuario,efectivo,cheque,dolares,transferencia_nat,transferencia_mai,otro,total_fisico,total_general,cerrado,hora_cierre FROM cierres_caja WHERE usuario=%s ORDER BY id DESC LIMIT 20",(usuario,))
    cierres=c.fetchall();conn.close()
    medios_hoy=[("Efectivo",tot_hoy["Efectivo"],"efectivo"),("Cheque",tot_hoy["Cheque"],"cheque"),("Dólares",tot_hoy["Dólares"],"dolares"),("Nat.",tot_hoy["Transferencia → Natasha Carlon"],"transferencia"),("Maira",tot_hoy["Transferencia → Maira Carlon"],"transferencia"),("Otro",tot_hoy["Otro"],"")]
    items_hoy="".join(f'<div class="caja-item {cls}"><span class="ci-label">{lb}</span><span class="ci-val">{fmt(v)}</span></div>' for lb,v,cls in medios_hoy if v>0 or lb in ("Efectivo","Nat."))
    items_hoy+=f'<div class="caja-item total-fisico"><span class="ci-label">Físico</span><span class="ci-val">{fmt(tot_hoy["total_fisico"])}</span></div>'
    estado_badge='<span class="estado-cerrada">✓ Cerrada</span>' if ya_cerro else '<span class="estado-abierta">● Abierta</span>'
    cierre_html=""
    for ci in cierres:
        fecha_ci,usr_ci,ef,ch,dol,nat,mai,otro,tf,tg,cerr,hora=ci
        medios_ci=[("Ef",ef,"efectivo"),("Ch",ch,"cheque"),("U$S",dol,"dolares"),("Nat",nat,"transferencia"),("Maira",mai,"transferencia"),("Otro",otro,"")]
        items_ci="".join(f'<div class="caja-item {cls}" style="min-width:60px;padding:5px 8px"><span class="ci-label">{lb}</span><span class="ci-val" style="font-size:.9rem">{fmt(v)}</span></div>' for lb,v,cls in medios_ci if v>0)
        items_ci+=f'<div class="caja-item total-fisico" style="min-width:60px;padding:5px 8px"><span class="ci-label">Total</span><span class="ci-val" style="font-size:.9rem">{fmt(tg)}</span></div>'
        est='<span class="estado-cerrada">✓ {hora}</span>' if cerr else '<span class="estado-abierta">Abierta</span>'
        cierre_html+=f'<div class="caja-row {"" if cerr else ""}"><div class="caja-header"><div><span class="caja-user">{usr_ci}</span><span class="caja-fecha"> · {fecha_ci}</span></div>{est}</div><div class="caja-medios">{items_ci}</div></div>'
    btn_cierre='' if ya_cerro else '<form method="post"><input type="hidden" name="accion" value="cerrar_caja"><button class="btn btn-r" onclick="return confirm(\'¿Cerrar caja del día?\')">Cerrar Caja Hoy</button></form>'
    body=f"""
    <h1 class="page-title">Caja Diaria</h1><p class="page-sub">Cobros del día — {usuario} · {fecha_hoy}</p>{flash}
    <div class="caja-row" style="margin-bottom:18px">
      <div class="caja-header"><div><span class="caja-user">Mi caja hoy</span></div>{estado_badge}</div>
      <div class="caja-medios">{items_hoy}</div>
      <div style="margin-top:12px">{btn_cierre}</div>
    </div>
    <div class="fcard"><h3>Historial de cierres</h3>{cierre_html or '<p style="color:var(--muted);font-size:.84rem">Sin cierres</p>'}</div>"""
    return page("Caja",body,"Caja")

# ══════════════════════════════════════════════════════════════════════════════
#  REPORTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/reportes")
@admin_req
def reportes():
    conn=conectar();c=conn.cursor()
    c.execute("SELECT periodo,COALESCE(SUM(debe),0),COALESCE(SUM(haber),0),COALESCE(SUM(debe-haber),0) FROM cuentas GROUP BY periodo ORDER BY SUBSTRING(periodo,4,4) DESC,SUBSTRING(periodo,1,2) DESC LIMIT 20")
    por_mes=c.fetchall()
    c.execute("SELECT cl.nombre,SUM(cu.debe),SUM(cu.haber),SUM(cu.debe-cu.haber) d FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id GROUP BY cl.nombre ORDER BY SUM(cu.debe-cu.haber) DESC LIMIT 20")
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
    sin_abono=c.fetchall();conn.close()
    filas_mes="".join(f'<tr><td class="nm">{r[0]}</td><td>{fmt(r[1])}</td><td style="color:var(--success);font-weight:600">{fmt(r[2])}</td><td style="color:{"var(--danger)" if (r[3] or 0)>0 else "var(--success)"};font-weight:600">{fmt(r[3] or 0)}</td></tr>' for r in por_mes)
    filas_rank="".join(f'<tr><td class="nm">{r[0]}</td><td>{fmt(r[1])}</td><td style="color:var(--success)">{fmt(r[2])}</td><td style="color:{"var(--danger)" if (r[3] or 0)>0 else "var(--success)"}"><b>{fmt(r[3] or 0)}</b></td></tr>' for r in ranking)
    filas_medio="".join(f'<tr><td class="nm"><span class="bmedio">{r[0]}</span></td><td style="font-weight:600;color:var(--success)">{fmt(r[1])}</td><td class="mu">{r[2]} pagos</td></tr>' for r in por_medio)
    filas_gastos="".join(f'<tr><td class="nm">{r[0]}</td><td style="color:var(--danger);font-weight:600">{fmt(r[1])}</td></tr>' for r in gastos_cat)
    filas_aud="".join(f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[0]}</span><span class="log-user">{a[1]}</span><span class="log-msg"><b>{a[2]}</b>{" - "+a[4] if a[4] else ""} - {a[3]}</span></div>' for a in auditoria)
    sin_ab=f'<div class="warn-box">{len(sin_abono)} clientes sin honorarios: {", ".join(s[0] for s in sin_abono[:12])}</div>' if sin_abono else ""
    total_s=nat+mai;pct_nat=int(nat/total_s*100) if total_s>0 else 50;pct_mai=100-pct_nat
    body=f"""
    <h1 class="page-title">Reportes</h1><p class="page-sub">Resúmenes financieros y auditoría</p>{sin_ab}
    <div class="fcard"><h3>Distribución entre Socias</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:12px" class="twocol">
        <div style="text-align:center;padding:14px;background:#f0f9f4;border-radius:10px">
          <div style="font-weight:600;color:var(--primary);margin-bottom:6px">Natasha Carlon</div>
          <div style="font-family:'DM Serif Display',serif;font-size:1.8rem;color:var(--primary)">{fmt(nat)}</div>
          <div style="font-size:.74rem;color:var(--muted)">{pct_nat}% del total</div>
        </div>
        <div style="text-align:center;padding:14px;background:#f0f4ff;border-radius:10px">
          <div style="font-weight:600;color:var(--info);margin-bottom:6px">Maira Carlon</div>
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
      <button class="tab on" onclick="showTab('t1',this)">Por Periodo</button>
      <button class="tab" onclick="showTab('t2',this)">Clientes</button>
      <button class="tab" onclick="showTab('t3',this)">Medios de Pago</button>
      <button class="tab" onclick="showTab('t4',this)">Gastos</button>
      <button class="tab" onclick="showTab('t5',this)">Auditoría</button>
    </div>
    <div id="t1" class="tabpanel on"><div class="dtable"><table><thead><tr><th>Periodo</th><th>Facturado</th><th>Cobrado</th><th>Deuda</th></tr></thead><tbody>{filas_mes or "<tr><td colspan=4 style='color:var(--muted);text-align:center;padding:20px'>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t2" class="tabpanel"><div class="dtable"><table><thead><tr><th>Cliente</th><th>Facturado</th><th>Cobrado</th><th>Saldo</th></tr></thead><tbody>{filas_rank or "<tr><td colspan=4 style='color:var(--muted);text-align:center;padding:20px'>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t3" class="tabpanel"><div class="dtable"><table><thead><tr><th>Medio</th><th>Total</th><th>Cant.</th></tr></thead><tbody>{filas_medio or "<tr><td colspan=3 style='color:var(--muted);text-align:center;padding:20px'>Sin datos</td></tr>"}</tbody></table></div></div>
    <div id="t4" class="tabpanel"><div class="dtable"><table><thead><tr><th>Categoría</th><th>Total</th></tr></thead><tbody>{filas_gastos or "<tr><td colspan=2 style='color:var(--muted);text-align:center;padding:20px'>Sin gastos</td></tr>"}</tbody></table></div></div>
    <div id="t5" class="tabpanel"><div class="fcard"><h3>Registro completo</h3>{filas_aud or "<p style='color:var(--muted);font-size:.84rem'>Sin actividad</p>"}</div></div>
    <script>function showTab(id,btn){{document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));document.getElementById(id).classList.add('on');btn.classList.add('on')}}</script>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Reportes",body,"Reportes")

# ══════════════════════════════════════════════════════════════════════════════
#  USUARIOS (redirige a configuracion)
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/usuarios")
@admin_req
def usuarios():
    return redirect("/configuracion")

# ══════════════════════════════════════════════════════════════════════════════
#  PDF RECIBOS
# ══════════════════════════════════════════════════════════════════════════════
def generar_pdf(cliente_id, periodo, monto):
    buffer=BytesIO();cv=canvas.Canvas(buffer,pagesize=A4);w,h=A4
    conn=conectar();c=conn.cursor()
    c.execute("SELECT nombre,cuit FROM clientes WHERE id=%s",(cliente_id,))
    data=c.fetchone();conn.close()
    cli_nombre=data[0] if data else "—";cuit_cli=dec(data[1]) if data else ""
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

# ══════════════════════════════════════════════════════════════════════════════
#  AGENDA VENCIMIENTOS
# ══════════════════════════════════════════════════════════════════════════════
MESES_ESP=["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

@app.route("/agenda")
@login_req
def agenda():
    mes=int(request.args.get("mes",datetime.now().month))
    anio=int(request.args.get("anio",datetime.now().year))
    conn=conectar();c=conn.cursor()
    c.execute("SELECT vencimiento_id,estado,nota,usuario,fecha_actualizacion FROM agenda_vencimientos WHERE mes=%s AND anio=%s",(mes,anio))
    rows={r[0]:r for r in c.fetchall()}
    c.execute("SELECT vencimiento_id,estado,nota,usuario,fecha_actualizacion FROM agenda_vencimientos WHERE mes=%s AND anio=%s ORDER BY fecha_actualizacion DESC LIMIT 8",(mes,anio))
    actividad=c.fetchall();conn.close()
    hoy=datetime.now();dia_hoy=hoy.day if hoy.month==mes and hoy.year==anio else 0
    stats={"total":len(VENCIMIENTOS_IMPOSITIVOS),"pendiente":0,"borrador":0,"presentado":0,"observado":0}
    alertas=[]
    filas=""
    for v in VENCIMIENTOS_IMPOSITIVOS:
        row=rows.get(v["id"])
        estado=row[1] if row else "pendiente"
        nota=row[2] if row else ""
        stats[estado]=stats.get(estado,0)+1
        dias_rest=v["dia"]-dia_hoy if dia_hoy>0 else 99
        if estado=="pendiente" and 0<dias_rest<=5:
            alertas.append(f"⚠️ <b>{v['nombre']}</b> vence en {dias_rest} día(s) (día {v['dia']})")
        elif estado=="pendiente" and dias_rest<=0 and dia_hoy>0:
            alertas.append(f"🔴 <b>{v['nombre']}</b> venció el día {v['dia']} y está pendiente")
        estados_opts="".join(f'<option value="{s}" {"selected" if s==estado else ""}>{l}</option>' for s,l in [("pendiente","⏳ Pendiente"),("borrador","📝 En borrador"),("presentado","✅ Presentado"),("observado","⚠ Observado")])
        tipo_badge=f'<span style="font-size:.68rem;padding:2px 7px;border-radius:8px;background:{"#f0f4ff" if v["tipo"]=="AFIP" else "#f0f9f4"};color:{"#1a3a8a" if v["tipo"]=="AFIP" else "#1a5c3a"};font-weight:600">{v["tipo"]}</span>'
        venc_badge=f'<span style="font-size:.72rem;color:var(--muted)">Día {v["dia"]}</span>'
        color_est={"pendiente":"var(--border)","borrador":"var(--warning)","presentado":"var(--success)","observado":"var(--danger)"}.get(estado,"var(--border)")
        filas+=f'''<div style="background:var(--card);border-radius:var(--r);padding:14px 18px;box-shadow:var(--shadow);margin-bottom:9px;border-left:4px solid {color_est}">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <div><span style="font-weight:600;color:var(--primary)">{v["nombre"]}</span> {tipo_badge} {venc_badge}</div>
            <form method="post" action="/agenda/actualizar" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
              <input type="hidden" name="venc_id" value="{v["id"]}">
              <input type="hidden" name="mes" value="{mes}">
              <input type="hidden" name="anio" value="{anio}">
              <div class="fg" style="min-width:160px"><select name="estado" style="font-size:.82rem">{estados_opts}</select></div>
              <div class="fg" style="flex:1;min-width:180px"><input name="nota" value="{nota}" placeholder="Nota..." style="font-size:.82rem"></div>
              <button type="submit" class="btn btn-p btn-sm">Guardar</button>
            </form>
          </div>
        </div>'''
    act_html=""
    NOMBRES_V={v["id"]:v["nombre"] for v in VENCIMIENTOS_IMPOSITIVOS}
    for a in actividad:
        ESTADOS_LABELS2={"pendiente":"Pendiente","borrador":"En borrador","presentado":"Presentado","observado":"Observado"}
        act_html+=f'<div class="logrow"><div class="log-dot"></div><span class="log-time">{a[4]}</span><span class="log-user">{a[3]}</span><span class="log-msg"><b>{NOMBRES_V.get(a[0],a[0])}</b> → {ESTADOS_LABELS2.get(a[1],a[1])}{" · "+a[2] if a[2] else ""}</span></div>'
    alerta_html='<div class="warn-box" style="margin-bottom:16px">'+"<br>".join(alertas)+"</div>" if alertas else ""
    pct_pres=int(stats["presentado"]/stats["total"]*100) if stats["total"]>0 else 0
    mes_ant,anio_ant=(mes-1,anio) if mes>1 else (12,anio-1)
    mes_sig,anio_sig=(mes+1,anio) if mes<12 else (1,anio+1)
    body=f"""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:5px">
      <h1 class="page-title">Agenda de Vencimientos</h1>
      <div style="display:flex;align-items:center;gap:8px">
        <a href="/agenda?mes={mes_ant}&anio={anio_ant}" class="btn btn-o btn-sm">← Ant.</a>
        <span style="font-family:'DM Serif Display',serif;font-size:1.1rem;color:var(--primary);min-width:160px;text-align:center">{MESES_ESP[mes]} {anio}</span>
        <a href="/agenda?mes={mes_sig}&anio={anio_sig}" class="btn btn-o btn-sm">Sig. →</a>
      </div>
    </div>
    <p class="page-sub">Control de vencimientos impositivos · Santiago del Estero</p>
    {alerta_html}
    <div class="stats" style="margin-bottom:18px">
      <div class="scard"><div class="slabel">Total</div><div class="sval">{stats["total"]}</div></div>
      <div class="scard g"><div class="slabel">Presentados</div><div class="sval">{stats["presentado"]}</div></div>
      <div class="scard b"><div class="slabel">En borrador</div><div class="sval">{stats["borrador"]}</div></div>
      <div class="scard r"><div class="slabel">Pendientes</div><div class="sval">{stats["pendiente"]}</div></div>
    </div>
    <div class="fcard" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:.82rem">
        <span style="font-weight:600;color:var(--primary)">Progreso del mes</span>
        <span style="color:var(--success);font-weight:700">{pct_pres}% presentado</span>
      </div>
      <div class="progwrap"><div class="progbar" style="width:{pct_pres}%"></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 320px;gap:16px;align-items:start" class="twocol">
      <div>{filas}</div>
      <div>
        <div class="fcard"><h3>🕓 Actividad reciente</h3>{act_html or "<p style='color:var(--muted);font-size:.84rem'>Sin actividad</p>"}</div>
        <div class="info-box"><b>Leyenda:</b><br>⏳ Pendiente · 📝 Borrador · ✅ Presentado · ⚠ Observado</div>
      </div>
    </div>
    <style>@media(max-width:700px){{.twocol{{grid-template-columns:1fr!important}}}}</style>"""
    return page("Agenda", body, "Agenda")

@app.route("/agenda/actualizar", methods=["POST"])
@login_req
def agenda_actualizar():
    venc_id=request.form.get("venc_id","").strip()
    mes=int(request.form.get("mes",datetime.now().month))
    anio=int(request.form.get("anio",datetime.now().year))
    estado=request.form.get("estado","pendiente")
    nota=request.form.get("nota","").strip()
    ids_validos={v["id"] for v in VENCIMIENTOS_IMPOSITIVOS}
    if venc_id not in ids_validos: return redirect(f"/agenda?mes={mes}&anio={anio}")
    conn=conectar();c=conn.cursor()
    c.execute("""INSERT INTO agenda_vencimientos(vencimiento_id,mes,anio,estado,nota,usuario,fecha_actualizacion)
                 VALUES(%s,%s,%s,%s,%s,%s,%s)
                 ON CONFLICT(vencimiento_id,mes,anio)
                 DO UPDATE SET estado=%s,nota=%s,usuario=%s,fecha_actualizacion=%s""",
              (venc_id,mes,anio,estado,nota,session.get("display",""),now_ar(),
               estado,nota,session.get("display",""),now_ar()))
    conn.commit();conn.close()
    nombre_v=next((v["nombre"] for v in VENCIMIENTOS_IMPOSITIVOS if v["id"]==venc_id),venc_id)
    registrar_auditoria("AGENDA",f"{nombre_v} → {estado}")
    return redirect(f"/agenda?mes={mes}&anio={anio}")

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTAR
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/importar", methods=["GET","POST"])
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
            c.execute("INSERT INTO clientes(nombre,cuit,telefono,abono) VALUES(%s,%s,%s,%s)",
                      (nombre,enc(str(row.get("cuit",""))),enc(str(row.get("telefono",""))),row.get("honorario",0)));ok+=1
        conn.commit();conn.close();registrar_auditoria("IMPORTACIÓN",f"{ok} clientes importados")
        return redirect("/clientes")
    body='<h1 class="page-title">Importar Clientes</h1><p class="page-sub">Excel con columnas: <b>nombre y apellido</b>, cuit, telefono, honorario</p><div class="fcard"><h3>📂 Archivo Excel</h3><form method="post" enctype="multipart/form-data"><div class="fg" style="margin-bottom:14px"><label>Archivo .xlsx</label><input type="file" name="archivo" accept=".xlsx,.xls"></div><button class="btn btn-p">Importar</button></form></div>'
    return page("Importar",body)

if __name__=="__main__":
    app.run(debug=True)
