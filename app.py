# ══════════════════════════════════════════════════════
#  ASISTENTE IA — ESTUDIO CARLON
#  Agregar estas dos partes al app.py
# ══════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────
# PARTE 1: Importaciones adicionales necesarias
# Agregar al inicio del archivo, junto a los otros imports
# ─────────────────────────────────────────────────────
import json
import urllib.request

# ─────────────────────────────────────────────────────
# PARTE 2: Ruta /asistente
# Agregar antes de la línea: if __name__=="__main__":
# ─────────────────────────────────────────────────────

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
                   ("/gastos","Gastos"),("/caja","Caja"),("/reportes","Reportes"),("/usuarios","Usuarios")]
    links_sec = [("/clientes","Clientes"),("/deudas","Deudores"),("/gastos","Gastos"),("/caja","Caja")]
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
    return f'<nav><span class="brand">✦ Estudio Carlon</span><div class="nav-links">{items}</div><div class="user-pill">👤 {disp} {badge}</div></nav>{asistente_widget}'
