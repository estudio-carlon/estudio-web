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
