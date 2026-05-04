# ══════════════════════════════════════════════════════
#  AGENDA DE VENCIMIENTOS IMPOSITIVOS — ESTUDIO CARLON
#  Agregar al app.py
# ══════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────
# PASO 1: En init_db(), agregar esta tabla nueva
# Dentro del bloque de c.execute existentes:
# ─────────────────────────────────────────────────────

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
# ↑ Pegar ese c.execute(...) dentro de init_db(), junto a los otros CREATE TABLE


# ─────────────────────────────────────────────────────
# PASO 2: Lista de vencimientos fijos del estudio
# Agregar como constante global, después de CATEGORIAS_GASTO
# ─────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────
# PASO 3: Rutas de la agenda
# Agregar antes de if __name__=="__main__":
# ─────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────
# PASO 4: Agregar "Agenda" al menú de navegación
# En nav_html(), modificar links_admin así:
# ─────────────────────────────────────────────────────

# links_admin = [
#     ("/panel","Panel"),
#     ("/clientes","Clientes"),
#     ("/deudas","Deudores"),
#     ("/gastos","Gastos"),
#     ("/caja","Caja"),
#     ("/reportes","Reportes"),
#     ("/agenda","Agenda"),       ← AGREGAR ESTA LÍNEA
#     ("/usuarios","Usuarios")
# ]

# ─────────────────────────────────────────────────────
# PASO 5 (opcional): Agregar Agenda también al menú de secretarias
# ─────────────────────────────────────────────────────

# links_sec = [
#     ("/clientes","Clientes"),
#     ("/deudas","Deudores"),
#     ("/gastos","Gastos"),
#     ("/caja","Caja"),
#     ("/agenda","Agenda"),       ← AGREGAR ESTA LÍNEA
# ]
