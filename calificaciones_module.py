"""Vencimientos de calificaciones bancarias de clientes.

- Tabla calificaciones_bancarias (cliente, banco, monto calificado, fecha de vencimiento).
- Pagina /calificaciones para alta, edicion y baja.
- alerta_calificaciones_html(): bloque de alertas para el Panel admin y el Panel de secretarias,
  que muestra las calificaciones que vencen dentro de los proximos DIAS_AVISO dias (o ya vencidas).
"""
from datetime import date, datetime
from html import escape as _e

DIAS_AVISO = 30

DATOS_INICIALES = [
    # (patron de busqueda del cliente, nombre a mostrar si no se encuentra, banco, monto, vencimiento)
    ("%leguizam%", "LEGUIZAMÓN HÉCTOR ALBERTO", "Banco Nación", 1410958000, date(2027, 3, 31)),
    ("%leguizam%", "LEGUIZAMÓN HÉCTOR ALBERTO", "Banco Galicia", 600000000, date(2027, 2, 12)),
]


def _hoy():
    from app import now_ar_dt
    return now_ar_dt().date()


def _fecha_txt(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _filas_por_vencer(dias=DIAS_AVISO):
    """Devuelve [(id, cliente, banco, monto, vencimiento, dias_restantes)] que vencen en <= dias."""
    from app import conectar
    hoy = _hoy()
    conn = conectar(); c = conn.cursor()
    c.execute("""SELECT cb.id, COALESCE(cl.nombre, cb.cliente_nombre), cb.banco, cb.monto, cb.fecha_vencimiento
                 FROM calificaciones_bancarias cb
                 LEFT JOIN clientes cl ON cl.id = cb.cliente_id
                 WHERE cb.fecha_vencimiento <= %s
                 ORDER BY cb.fecha_vencimiento""", (date.fromordinal(hoy.toordinal() + dias),))
    filas = [(r[0], r[1], r[2], r[3], r[4], (r[4] - hoy).days) for r in c.fetchall()]
    conn.close()
    return filas


def alerta_calificaciones_html():
    """Bloque HTML de alerta para los paneles. Vacio si no hay nada por vencer."""
    from app import fmt
    try:
        filas = _filas_por_vencer()
    except Exception:
        return ""
    if not filas:
        return ""
    items = ""
    for _id, cli, banco, monto, venc, dr in filas:
        if dr < 0:
            badge = f'<span class="sec-badge danger">VENCIDA hace {-dr} día(s)</span>'
        elif dr == 0:
            badge = '<span class="sec-badge danger">VENCE HOY</span>'
        else:
            badge = f'<span class="sec-badge {"danger" if dr <= 7 else "warn"}">vence en {dr} día(s)</span>'
        items += (f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;'
                  f'padding:6px 0;border-bottom:1px solid var(--border);flex-wrap:wrap">'
                  f'<span style="font-size:.82rem"><b>{_e(cli or "?")}</b> · {_e(banco or "")} · {fmt(monto)}'
                  f' <span style="color:var(--muted)">({_fecha_txt(venc)})</span></span>{badge}</div>')
    return (f'<div class="warn-box" style="margin-bottom:14px"><b>🏦 Calificaciones bancarias por vencer ({len(filas)})</b>'
            f' · <a href="/calificaciones" style="color:#7a5800;font-weight:600">Ver todas</a>{items}</div>')


def register_calificaciones(app):
    from flask import request, redirect, session
    from app import conectar, fmt, registrar_auditoria, login_req, page, now_ar

    def _init_db():
        conn = conectar(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS calificaciones_bancarias(
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
            cliente_nombre TEXT DEFAULT '',
            banco TEXT NOT NULL,
            monto NUMERIC(18,2) DEFAULT 0,
            fecha_vencimiento DATE NOT NULL,
            observaciones TEXT DEFAULT '',
            usuario TEXT,
            fecha_actualizacion TEXT)""")
        # Carga inicial: corre una sola vez (marcada en config_seguridad) para que,
        # si despues se borra o edita un registro, no se vuelva a recrear.
        c.execute("""CREATE TABLE IF NOT EXISTS config_seguridad(
            id SERIAL PRIMARY KEY,clave TEXT UNIQUE,valor TEXT)""")
        c.execute("INSERT INTO config_seguridad(clave,valor) VALUES('calif_seed_v1','1') ON CONFLICT(clave) DO NOTHING RETURNING id")
        primera_vez = c.fetchone() is not None
        for patron, nombre_def, banco, monto, venc in (DATOS_INICIALES if primera_vez else []):
            c.execute("SELECT id, nombre FROM clientes WHERE nombre ILIKE %s ORDER BY id LIMIT 1", (patron,))
            cl = c.fetchone()
            cid = cl[0] if cl else None
            nombre = cl[1] if cl else nombre_def
            c.execute("""SELECT 1 FROM calificaciones_bancarias
                         WHERE (cliente_id=%s OR cliente_nombre ILIKE %s) AND banco=%s""",
                      (cid, patron, banco))
            if not c.fetchone():
                c.execute("""INSERT INTO calificaciones_bancarias(cliente_id,cliente_nombre,banco,monto,
                             fecha_vencimiento,usuario,fecha_actualizacion) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                          (cid, nombre, banco, monto, venc, "carga inicial", now_ar()))
        conn.commit(); c.close(); conn.close()

    _init_db()

    def _parse_monto(txt):
        # Acepta "1.410.958.000", "1410958000", "600.000.000,50"
        t = (txt or "").strip().replace("$", "").replace(" ", "")
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif t.count(".") > 1 or (t.count(".") == 1 and len(t.split(".")[1]) == 3):
            t = t.replace(".", "")
        try:
            return float(t or 0)
        except ValueError:
            return None

    @app.route("/calificaciones", methods=["GET"])
    @login_req
    def calificaciones_vista():
        hoy = _hoy()
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT id, nombre FROM clientes WHERE activo IS NOT FALSE ORDER BY nombre")
        clientes = c.fetchall()
        c.execute("""SELECT cb.id, cb.cliente_id, COALESCE(cl.nombre, cb.cliente_nombre), cb.banco, cb.monto,
                            cb.fecha_vencimiento, COALESCE(cb.observaciones,''), COALESCE(cb.usuario,''),
                            COALESCE(cb.fecha_actualizacion,'')
                     FROM calificaciones_bancarias cb
                     LEFT JOIN clientes cl ON cl.id = cb.cliente_id
                     ORDER BY cb.fecha_vencimiento""")
        filas = c.fetchall()
        conn.close()

        editar_id = request.args.get("editar", type=int)
        edit = next((f for f in filas if f[0] == editar_id), None)

        n_alerta = 0
        trs = ""
        for cid_row, cli_id, cli, banco, monto, venc, obs, usr, fact in filas:
            dr = (venc - hoy).days
            if dr < 0:
                badge = f'<span class="sec-badge danger">Vencida ({-dr} d)</span>'; n_alerta += 1
            elif dr <= DIAS_AVISO:
                badge = f'<span class="sec-badge {"danger" if dr <= 7 else "warn"}">{"Hoy" if dr == 0 else f"{dr} días"}</span>'; n_alerta += 1
            else:
                badge = f'<span class="sec-badge" style="background:#1D9E7522;color:#1D9E75">Vigente · {dr} días</span>'
            trs += (f'<tr><td class="nm">{_e(cli or "?")}</td><td>{_e(banco)}</td>'
                    f'<td style="text-align:right;font-weight:600">{fmt(monto)}</td>'
                    f'<td>{_fecha_txt(venc)}</td><td>{badge}</td>'
                    f'<td class="mu" style="font-size:.78rem">{_e(obs)}</td>'
                    f'<td style="white-space:nowrap">'
                    f'<a href="/calificaciones?editar={cid_row}#form" class="btn btn-xs btn-o" title="Editar / renovar">✏️</a> '
                    f'<form method="post" action="/calificaciones/borrar/{cid_row}" style="display:inline" '
                    f'onsubmit="return confirm(\'¿Eliminar la calificación de {_e(cli or "", quote=True)} con {_e(banco, quote=True)}?\')">'
                    f'<button class="btn btn-xs btn-r" title="Eliminar">🗑</button></form></td></tr>')
        if not trs:
            trs = '<tr><td colspan="7" style="color:var(--muted);text-align:center;padding:14px">Sin calificaciones cargadas</td></tr>'

        sel_cli = edit[1] if edit else None
        opts = '<option value="">— Elegir cliente —</option>' + "".join(
            f'<option value="{i}" {"selected" if i == sel_cli else ""}>{_e(n or "")}</option>' for i, n in clientes)
        v_banco = _e(edit[3]) if edit else ""
        v_monto = (f"{float(edit[4]):,.0f}".replace(",", ".")) if edit else ""
        v_venc = edit[5].isoformat() if edit else ""
        v_obs = _e(edit[6]) if edit else ""
        titulo_form = "Editar / renovar calificación" if edit else "Nueva calificación"
        cancelar = '<a href="/calificaciones" class="btn btn-o btn-sm">Cancelar</a>' if edit else ""

        body = f"""
        <h1 class="page-title">🏦 Calificaciones bancarias</h1>
        <p class="page-sub">Vencimientos de las calificaciones de clientes · la alerta aparece en los paneles {DIAS_AVISO} días antes del vencimiento</p>
        {'<div class="warn-box" style="margin-bottom:14px"><b>'+str(n_alerta)+'</b> calificación(es) vencen en los próximos '+str(DIAS_AVISO)+' días o ya vencieron</div>' if n_alerta else ''}
        <div class="fcard">
          <div class="dtable"><table>
            <thead><tr><th>Cliente</th><th>Banco</th><th style="text-align:right">Monto calificado</th>
            <th>Vencimiento</th><th>Estado</th><th>Obs.</th><th></th></tr></thead>
            <tbody>{trs}</tbody></table></div>
        </div>
        <div class="fcard" id="form">
          <h3>{titulo_form}</h3>
          <form method="post" action="/calificaciones/guardar">
            <input type="hidden" name="id" value="{edit[0] if edit else ''}">
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
              <div><label>Cliente</label><select name="cliente_id" required>{opts}</select></div>
              <div><label>Banco</label><input name="banco" value="{v_banco}" required placeholder="Banco Nación" list="bancos-lst"></div>
              <div><label>Monto calificado ($)</label><input name="monto" value="{v_monto}" required inputmode="decimal" placeholder="1.000.000"></div>
              <div><label>Fecha de vencimiento</label><input type="date" name="fecha_vencimiento" value="{v_venc}" required></div>
            </div>
            <div style="margin-top:10px"><label>Observaciones</label><input name="observaciones" value="{v_obs}" placeholder="Opcional"></div>
            <datalist id="bancos-lst"><option>Banco Nación</option><option>Banco Galicia</option><option>Banco Macro</option>
              <option>Banco Santander</option><option>Banco Ciudad</option><option>Banco Santiago del Estero</option><option>BBVA</option><option>Banco Credicoop</option></datalist>
            <div style="margin-top:12px;display:flex;gap:8px">
              <button class="btn btn-p btn-sm">Guardar</button>{cancelar}
            </div>
          </form>
        </div>"""
        return page("Calificaciones", body, "Calificaciones")

    @app.route("/calificaciones/guardar", methods=["POST"])
    @login_req
    def calificaciones_guardar():
        f = request.form
        try:
            cliente_id = int(f.get("cliente_id"))
            venc = datetime.strptime(f.get("fecha_vencimiento", ""), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return redirect("/calificaciones")
        banco = (f.get("banco") or "").strip()
        monto = _parse_monto(f.get("monto"))
        if not banco or monto is None:
            return redirect("/calificaciones")
        obs = (f.get("observaciones") or "").strip()
        usuario = session.get("display", session.get("user", "?"))
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT nombre FROM clientes WHERE id=%s", (cliente_id,))
        r = c.fetchone(); nombre = r[0] if r else ""
        rid = f.get("id", "").strip()
        if rid.isdigit():
            c.execute("""UPDATE calificaciones_bancarias SET cliente_id=%s, cliente_nombre=%s, banco=%s, monto=%s,
                         fecha_vencimiento=%s, observaciones=%s, usuario=%s, fecha_actualizacion=%s WHERE id=%s""",
                      (cliente_id, nombre, banco, monto, venc, obs, usuario, now_ar(), int(rid)))
            accion = "Edito"
        else:
            c.execute("""INSERT INTO calificaciones_bancarias(cliente_id,cliente_nombre,banco,monto,fecha_vencimiento,
                         observaciones,usuario,fecha_actualizacion) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (cliente_id, nombre, banco, monto, venc, obs, usuario, now_ar()))
            accion = "Cargo"
        conn.commit(); conn.close()
        registrar_auditoria("CALIFICACION_BANCARIA",
                            f"{accion} calificacion {banco} {fmt(monto)} vence {_fecha_txt(venc)}", cliente_id, nombre)
        return redirect("/calificaciones")

    @app.route("/calificaciones/borrar/<int:cid>", methods=["POST"])
    @login_req
    def calificaciones_borrar(cid):
        conn = conectar(); c = conn.cursor()
        c.execute("""SELECT COALESCE(cl.nombre, cb.cliente_nombre), cb.banco, cb.cliente_id FROM calificaciones_bancarias cb
                     LEFT JOIN clientes cl ON cl.id=cb.cliente_id WHERE cb.id=%s""", (cid,))
        r = c.fetchone()
        c.execute("DELETE FROM calificaciones_bancarias WHERE id=%s", (cid,))
        conn.commit(); conn.close()
        if r:
            registrar_auditoria("CALIFICACION_BANCARIA", f"Elimino calificacion {r[1]}", r[2], r[0] or "")
        return redirect("/calificaciones")
