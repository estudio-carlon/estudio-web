# ══════════════════════════════════════════════════════════════════════════════
#  MEJORAS: solicitudes de anulacion, backup, honorarios minimos CPCESE,
#           aumento masivo de honorarios y recordatorios de deuda por WhatsApp
# ══════════════════════════════════════════════════════════════════════════════
import csv, io, json, math, re, zipfile, urllib.parse
from html import escape as _esc


# ── Tabla de honorarios minimos eticos CPCESE (Res. 06/2026, vigente 01/07/2026) ─
#  (codigo, grupo, descripcion, monto, unidad)
HONORARIOS_SEED = [
    ("A1","Consultas","Consulta verbal",18800,"por consulta"),
    ("A2","Consultas","Consulta escrita",172615,"por consulta"),
    ("B","Trabajo técnico","Hora de trabajo profesional",45900,"por hora"),
    ("D1_SCM_B","Impositiva","IVA - Ingresos Brutos sin Convenio Multilateral · facturación neta inferior a $8.159.250",124410,"mensual"),
    ("D1_SCM_A","Impositiva","IVA - Ingresos Brutos sin Convenio Multilateral · facturación neta superior a $8.159.250",203100,"mensual"),
    ("D1_CM_B","Impositiva","IVA - Ingresos Brutos con Convenio Multilateral · facturación neta inferior a $8.159.250",203100,"mensual"),
    ("D1_CM_A","Impositiva","IVA - Ingresos Brutos con Convenio Multilateral · facturación neta superior a $8.159.250",274050,"mensual"),
    ("D2_SCM_AE","Impositiva","Monotributo sin Convenio Multilateral · categorías A a E",68770,"mensual"),
    ("D2_SCM_FK","Impositiva","Monotributo sin Convenio Multilateral · categorías F a K",101660,"mensual"),
    ("D2_CM_AE","Impositiva","Monotributo con Convenio Multilateral · categorías A a E",137280,"mensual"),
    ("D2_CM_FK","Impositiva","Monotributo con Convenio Multilateral · categorías F a K",208900,"mensual"),
    ("D3_B","Impositiva","Ganancias / Bienes Personales · ingresos inferiores a $7.590.000 anuales",253750,"por impuesto anual"),
    ("D3_A","Impositiva","Ganancias / Bienes Personales · ingresos superiores a $7.590.000 anuales",380720,"por impuesto anual"),
    ("D4","Impositiva","Inscripciones",101670,"por impuesto, por organismo"),
    ("D5","Impositiva","Regímenes de información",106800,"por régimen"),
    ("D6","Impositiva","Planes de pago (o el 3% de la deuda capital, el mayor)",137280,"por plan"),
    ("D7","Impositiva","Contestación de requerimientos y/o inspecciones",228380,"por requerimiento"),
    ("E1","Laboral","Altas e inscripciones",137280,"por trámite"),
    ("E2_1","Laboral","Liquidación de sueldos · un empleado",68670,"mensual"),
    ("E2_ADIC","Laboral","Liquidación de sueldos · por cada empleado adicional",20415,"mensual"),
    ("E3","Laboral","Ganancias cuarta categoría (SIRADIG)",137280,"anual"),
    ("E4","Laboral","DDJJ patrimonial integral con anexo reservado",253750,"anual"),
    ("E5","Laboral","Contestación de requerimiento y/o inspecciones",228400,"por requerimiento"),
    ("F1","Certificaciones","Certificación de ingresos hasta $101.010 (superior: 3% del monto)",42550,"por certificación"),
    ("F2_MIN","Certificaciones","Certificación EECC entes sin fines de lucro (hasta $1.265.000)",289605,"mínimo"),
    ("F3_MIN","Certificaciones","Certificación EECC con fines de lucro (hasta $1.265.000)",492490,"mínimo"),
    ("F7","Certificaciones","Certificación de origen de fondos (o el 1% del monto, el mayor)",143980,"por certificación"),
    ("F8","Certificaciones","Encargos de procedimientos acordados (o el 1% del monto, el mayor)",150150,"por certificación"),
    ("F9","Certificaciones","Otros servicios relacionados",59710,"mínimo"),
    ("H1","Constitución","Constitución e inscripción de sociedades, fideicomisos y otros entes",1370300,"por trámite"),
    ("H2","Constitución","Constitución e inscripción de entes sin fines de lucro y cooperativas",1014900,"por trámite"),
    ("H3","Constitución","Carpetas para licitaciones (o el 0,5% de la oferta, el mayor)",253750,"por carpeta"),
]
HM_META_DEFAULT = {
    "hm_resolucion": "06/2026",
    "hm_vigencia": "01/07/2026",
    "hm_pdf": "https://cpcese.org.ar/documentos/Contador%20Publico%20R.%2006-2026%20.pdf",
}
# Tramo de honorario mensual que se usa para recomendar el abono de cada cliente
TRAMOS = [
    ("AUTO","Automático (según condición fiscal)"),
    ("D1_SCM_B","RI sin CM · fact. < $8,16 M"),
    ("D1_SCM_A","RI sin CM · fact. > $8,16 M"),
    ("D1_CM_B","RI con CM · fact. < $8,16 M"),
    ("D1_CM_A","RI con CM · fact. > $8,16 M"),
    ("D2_SCM_AE","Monotributo sin CM · A a E"),
    ("D2_SCM_FK","Monotributo sin CM · F a K"),
    ("D2_CM_AE","Monotributo con CM · A a E"),
    ("D2_CM_FK","Monotributo con CM · F a K"),
    ("NINGUNO","No aplica (sin recomendación)"),
]
MSG_RECORDATORIO_DEFAULT = (
    "Hola {nombre}, le recordamos desde el Estudio Contable Carlon que registra un saldo pendiente "
    "de {saldo} ({periodos}). Puede abonar por transferencia al alias ESTUDIO.CONTA.CARLON o en el estudio. "
    "Si ya realizó el pago, desestime este mensaje. ¡Muchas gracias!"
)


def cod_vis(cod):
    """D1_SCM_B -> D.1 (codigo como figura en la tabla del Consejo)"""
    base = (cod or "").split("_")[0]
    return re.sub(r"^([A-Z])(\d+)$", r"\1.\2", base)


def _wa_num(tel):
    """Normaliza un telefono argentino para wa.me (54 + area + numero)."""
    d = re.sub(r"\D", "", tel or "")
    if not d: return ""
    if d.startswith("00"): d = d[2:]
    if d.startswith("54"): return d
    if d.startswith("0"): d = d[1:]
    return "54" + d


def register_mejoras(app):
    from flask import request, redirect, session, send_file
    import app as A
    conectar, fmt, now_ar, now_ar_dt = A.conectar, A.fmt, A.now_ar, A.now_ar_dt
    login_req, admin_req, page, dec = A.login_req, A.admin_req, A.page, A.dec
    registrar_auditoria = A.registrar_auditoria

    # ── Base de datos ─────────────────────────────────────────────────────────
    def _init():
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT pg_advisory_xact_lock(424243)")
        c.execute("CREATE TABLE IF NOT EXISTS app_config(clave TEXT PRIMARY KEY, valor TEXT)")
        c.execute("""CREATE TABLE IF NOT EXISTS honorarios_minimos(
            codigo TEXT PRIMARY KEY, grupo TEXT, descripcion TEXT, monto REAL, unidad TEXT, orden INTEGER)""")
        c.execute("SELECT COUNT(*) FROM honorarios_minimos")
        if c.fetchone()[0] == 0:
            for i, (cod, grp, desc, monto, uni) in enumerate(HONORARIOS_SEED):
                c.execute("INSERT INTO honorarios_minimos VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                          (cod, grp, desc, monto, uni, i))
        for k, v in HM_META_DEFAULT.items():
            c.execute("INSERT INTO app_config(clave,valor) VALUES(%s,%s) ON CONFLICT DO NOTHING", (k, v))
        c.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS tramo_honorario TEXT DEFAULT 'AUTO'")
        c.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS hon_incluye_sueldos BOOLEAN DEFAULT TRUE")
        c.execute("""CREATE TABLE IF NOT EXISTS recordatorios_deuda(
            id SERIAL PRIMARY KEY, cliente_id INTEGER, fecha TEXT, periodo_envio TEXT, usuario TEXT, saldo REAL)""")
        conn.commit(); conn.close()
    _init()

    def cfg_get(c, clave, default=""):
        c.execute("SELECT valor FROM app_config WHERE clave=%s", (clave,))
        r = c.fetchone()
        return r[0] if r and r[0] is not None else default

    def cfg_set(c, clave, valor):
        c.execute("""INSERT INTO app_config(clave,valor) VALUES(%s,%s)
                     ON CONFLICT(clave) DO UPDATE SET valor=EXCLUDED.valor""", (clave, valor))

    def periodo_actual():
        return now_ar_dt().strftime("%m/%Y")

    # ══════════════════════════════════════════════════════════════════════════
    #  1) SOLICITUDES DE ANULACION / MODIFICACION DE RECIBOS
    # ══════════════════════════════════════════════════════════════════════════
    def n_solicitudes_pendientes():
        try:
            conn = conectar(); c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM solicitudes_recibo WHERE estado='PENDIENTE'")
            n = c.fetchone()[0]; conn.close(); return n
        except Exception:
            return 0
    A.n_solicitudes_pendientes = n_solicitudes_pendientes

    @app.route("/solicitudes")
    @login_req
    def solicitudes():
        es_admin = session.get("rol") == "admin"
        conn = conectar(); c = conn.cursor()
        if es_admin:
            c.execute("""SELECT id,fecha,usuario,tipo,persona,resumen,motivo,estado,resuelto_por,fecha_resolucion,cliente_id
                         FROM solicitudes_recibo ORDER BY (estado='PENDIENTE') DESC, id DESC LIMIT 150""")
        else:
            c.execute("""SELECT id,fecha,usuario,tipo,persona,resumen,motivo,estado,resuelto_por,fecha_resolucion,cliente_id
                         FROM solicitudes_recibo WHERE usuario=%s ORDER BY id DESC LIMIT 60""",
                      (session.get("display", ""),))
        rows = c.fetchall(); conn.close()
        filas = ""
        for sid, fec, usr, tipo, pers, res, mot, est, rpor, rfec, cid in rows:
            if est == "PENDIENTE":
                badge = '<span class="sec-badge warn">⏳ Pendiente</span>'
            elif est == "APROBADA":
                badge = f'<span class="sec-badge ok">✅ Aprobada</span><br><span class="mu">{_esc(rpor or "")} · {_esc(rfec or "")}</span>'
            else:
                badge = f'<span class="sec-badge danger">✖ Rechazada</span><br><span class="mu">{_esc(rpor or "")} · {_esc(rfec or "")}</span>'
            acciones = ""
            if es_admin and est == "PENDIENTE":
                acciones = (f'<form method="post" action="/solicitudes/{sid}/aprobar" style="display:inline" '
                            f'onsubmit="return confirm(\'¿Aprobar? Se aplicará el cambio al recibo.\')">'
                            f'<button class="btn btn-xs btn-g">✔ Aprobar</button></form> '
                            f'<form method="post" action="/solicitudes/{sid}/rechazar" style="display:inline">'
                            f'<button class="btn btn-xs btn-r">✖ Rechazar</button></form>')
            cuenta = f' <a href="/cuenta/{cid}" class="btn btn-xs btn-o">Ver cuenta</a>' if cid else ""
            filas += (f'<tr><td class="mu">{_esc(fec or "")}</td><td>{_esc(usr or "")}</td>'
                      f'<td class="nm">{_esc(pers or "")}{cuenta}</td><td>{_esc(res or "")}</td>'
                      f'<td class="mu">{_esc(mot or "")}</td><td>{badge}</td><td style="white-space:nowrap">{acciones}</td></tr>')
        intro = ("Las secretarias no pueden borrar ni modificar recibos directamente: envían una solicitud y "
                 "el cambio se aplica recién cuando la aprobás." if es_admin else
                 "Para borrar o modificar un recibo se envía una solicitud al administrador. Acá ves el estado de las tuyas.")
        body = f"""
        <a href="/caja" class="btn btn-o btn-sm" style="margin-bottom:14px">&larr; Caja</a>
        <h1 class="page-title">✋ Solicitudes de recibos</h1>
        <p class="page-sub">{intro}</p>
        <div class="fcard"><div class="dtable"><table>
          <thead><tr><th>Fecha</th><th>Pidió</th><th>Recibo de</th><th>Qué pide</th><th>Motivo</th><th>Estado</th><th></th></tr></thead>
          <tbody>{filas or "<tr><td colspan=7 style='text-align:center;color:var(--muted);padding:20px'>No hay solicitudes</td></tr>"}</tbody>
        </table></div></div>"""
        return page("Solicitudes", body, "Caja")

    @app.route("/solicitudes/<int:sid>/<accion>", methods=["POST"])
    @admin_req
    def resolver_solicitud(sid, accion):
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT tipo,cliente_id,persona,datos,motivo,usuario,estado,resumen FROM solicitudes_recibo WHERE id=%s FOR UPDATE", (sid,))
        r = c.fetchone()
        if not r or r[6] != "PENDIENTE":
            conn.close(); return redirect("/solicitudes")
        tipo, cid, persona, datos, motivo, solicitante, _est, resumen = r
        admin = session.get("display", "")
        if accion == "aprobar":
            d = json.loads(datos or "{}")
            det = f"Pedido por {solicitante} · Motivo: {motivo} · Aprobado por {admin}"
            if tipo == "BORRAR_PERIODOS":
                A._exec_borrar_periodos(c, cid, d.get("periodos", []), det, usuario=solicitante, rol="secretaria")
            elif tipo == "EDITAR_PAGO":
                A._exec_editar_pago(c, d["pago_id"], d["periodo"], float(d["monto"]), d["medio"], d.get("obs", ""),
                                    det, usuario=solicitante, rol="secretaria")
            elif tipo == "BORRAR_OCASIONAL":
                A._exec_borrar_ocasional(c, d["pago_id"], det, usuario=solicitante, rol="secretaria")
            estado = "APROBADA"
        else:
            estado = "RECHAZADA"
        c.execute("UPDATE solicitudes_recibo SET estado=%s,resuelto_por=%s,fecha_resolucion=%s WHERE id=%s",
                  (estado, admin, now_ar(), sid))
        conn.commit(); conn.close()
        registrar_auditoria("SOLICITUD " + estado, f"{resumen} · pedido por {solicitante}", cid, persona)
        return redirect("/solicitudes")

    # ══════════════════════════════════════════════════════════════════════════
    #  2) COPIA DE SEGURIDAD
    # ══════════════════════════════════════════════════════════════════════════
    def html_alerta_backup():
        """Aviso en el Panel si hace mas de 7 dias que no se descarga una copia."""
        try:
            conn = conectar(); c = conn.cursor()
            ult = cfg_get(c, "ultimo_backup", ""); conn.close()
        except Exception:
            return ""
        dias = None
        if ult:
            try: dias = (now_ar_dt().replace(tzinfo=None) - A.datetime.strptime(ult[:16], "%d/%m/%Y %H:%M")).days
            except Exception: dias = None
        if dias is not None and dias < 7:
            return ""
        txt = "Nunca se descargó una copia de seguridad" if not ult else f"La última copia de seguridad es del {ult} (hace {dias} días)"
        return (f'<div class="warn-box" style="margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">'
                f'<span>💾 <b>{txt}.</b> Conviene descargar una por semana y guardarla en tu Drive.</span>'
                f'<a href="/backup" class="btn btn-a btn-sm">Hacer copia ahora</a></div>')
    A.html_alerta_backup = html_alerta_backup

    @app.route("/backup")
    @admin_req
    def backup_page():
        conn = conectar(); c = conn.cursor()
        ult = cfg_get(c, "ultimo_backup", ""); ult_u = cfg_get(c, "ultimo_backup_usuario", "")
        c.execute("""SELECT table_name FROM information_schema.tables
                     WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""")
        tablas = [r[0] for r in c.fetchall()]
        resumen = ""
        for t in ("clientes", "cuentas", "pagos", "gastos", "empleados"):
            if t in tablas:
                c.execute(f'SELECT COUNT(*) FROM "{t}"'); resumen += f"<li>{t}: <b>{c.fetchone()[0]}</b> registros</li>"
        conn.close()
        body = f"""
        <h1 class="page-title">💾 Copia de seguridad</h1>
        <p class="page-sub">Descargá toda la información del sistema en un solo archivo.</p>
        <div class="fcard">
          <h3>Descargar copia completa</h3>
          <p style="font-size:.86rem;line-height:1.6;margin-bottom:10px">
            Se descarga un archivo <b>.zip</b> con:<br>
            • Una planilla <b>CSV por cada tabla</b> (clientes, cuentas, pagos, gastos, empleados, etc.) que se abre con Excel.<br>
            • Un archivo <b>backup.sql</b> para restaurar todo el sistema si alguna vez hiciera falta.</p>
          <ul style="font-size:.84rem;margin:0 0 12px 18px">{resumen}</ul>
          <p style="font-size:.82rem;color:var(--muted);margin-bottom:12px">
            Última copia: <b>{_esc(ult) if ult else "nunca"}</b>{(" · " + _esc(ult_u)) if ult_u else ""}</p>
          <a href="/backup/descargar" class="btn btn-g">⬇ Descargar copia de seguridad</a>
          <div class="warn-box" style="margin-top:14px;font-size:.8rem">
            🔒 El archivo contiene <b>todos los datos de los clientes</b> (CUIT, teléfonos, montos). Guardalo en tu Google Drive
            o en un pendrive, y no lo compartas.</div>
        </div>"""
        return page("Copia de seguridad", body, "Config")

    @app.route("/backup/descargar")
    @admin_req
    def backup_descargar():
        conn = conectar(); c = conn.cursor()
        c.execute("""SELECT table_name FROM information_schema.tables
                     WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""")
        tablas = [r[0] for r in c.fetchall()]
        buf = io.BytesIO()
        sql = io.StringIO()
        sql.write("-- Copia de seguridad Estudio Contable Carlon - " + now_ar() + "\n")
        sql.write("-- Para restaurar: con la app iniciada (tablas creadas), ejecutar este archivo con psql.\n")
        sql.write("BEGIN;\nSET session_replication_role = replica;\n")
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for t in tablas:
                c.execute(f'SELECT * FROM "{t}"')
                cols = [d[0] for d in c.description]
                rows = c.fetchall()
                # CSV legible (desencripta CUIT / telefonos)
                out = io.StringIO()
                w = csv.writer(out, delimiter=";")
                w.writerow(cols)
                for row in rows:
                    fila = []
                    for v in row:
                        if isinstance(v, str) and v.startswith("gAAAA"):
                            try: v = dec(v)
                            except Exception: pass
                        fila.append(v)
                    w.writerow(fila)
                z.writestr(f"tablas/{t}.csv", "﻿" + out.getvalue())
                # SQL restaurable (datos tal cual estan en la base)
                sql.write(f'\n-- {t} ({len(rows)} filas)\nDELETE FROM "{t}";\n')
                if rows:
                    col_sql = ",".join(f'"{x}"' for x in cols)
                    ph = "(" + ",".join(["%s"] * len(cols)) + ")"
                    for row in rows:
                        sql.write(f'INSERT INTO "{t}"({col_sql}) VALUES ' + c.mogrify(ph, row).decode("utf-8") + ";\n")
                if "id" in cols:
                    sql.write(f"SELECT setval(pg_get_serial_sequence('\"{t}\"','id'), COALESCE((SELECT MAX(id) FROM \"{t}\"),1));\n")
            sql.write("\nSELECT setval('recibo_seq', COALESCE((SELECT MAX(numero_recibo) FROM pagos),1));\n")
            sql.write("SET session_replication_role = DEFAULT;\nCOMMIT;\n")
            z.writestr("backup.sql", sql.getvalue())
            z.writestr("LEEME.txt",
                       "Copia de seguridad del sistema Estudio Contable Carlon\r\n"
                       f"Generada: {now_ar()} por {session.get('display','')}\r\n\r\n"
                       "- Carpeta 'tablas': una planilla CSV por tabla (abrir con Excel).\r\n"
                       "- backup.sql: restauracion completa de la base de datos (pedir ayuda tecnica para usarlo).\r\n")
        cfg_set(c, "ultimo_backup", now_ar())
        cfg_set(c, "ultimo_backup_usuario", session.get("display", ""))
        conn.commit(); conn.close()
        registrar_auditoria("BACKUP", f"Copia de seguridad descargada ({len(tablas)} tablas)")
        buf.seek(0)
        nombre = "backup_estudio_carlon_" + now_ar_dt().strftime("%Y-%m-%d_%H%M") + ".zip"
        return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=nombre)

    # ══════════════════════════════════════════════════════════════════════════
    #  3) HONORARIOS: tabla CPCESE, recomendaciones y aumento masivo
    # ══════════════════════════════════════════════════════════════════════════
    def tabla_hm(c):
        c.execute("SELECT codigo,grupo,descripcion,monto,unidad FROM honorarios_minimos ORDER BY orden,codigo")
        return c.fetchall()

    def recomendaciones(c):
        """Devuelve lista de dicts por cliente activo con su minimo segun la tabla."""
        hm = {r[0]: float(r[3] or 0) for r in tabla_hm(c)}
        c.execute("""SELECT cliente_id, COUNT(*) FROM empleados WHERE COALESCE(activo,TRUE)=TRUE GROUP BY cliente_id""")
        emp = dict(c.fetchall())
        c.execute("""SELECT id,nombre,COALESCE(condicion_fiscal,''),COALESCE(responsable_inscripto,FALSE),
                            COALESCE(abono,0),COALESCE(tramo_honorario,'AUTO'),COALESCE(hon_incluye_sueldos,TRUE)
                     FROM clientes WHERE COALESCE(activo,TRUE)=TRUE ORDER BY nombre""")
        out = []
        for cid, nom, cond, ri, abono, tramo, inc_s in c.fetchall():
            t = tramo
            if t == "AUTO":
                if "monotrib" in cond.lower(): t = "D2_SCM_AE"
                elif "responsable inscripto" in cond.lower() or ri: t = "D1_SCM_B"
                else: t = "NINGUNO"
            base = hm.get(t, 0) if t != "NINGUNO" else 0
            n_emp = int(emp.get(cid, 0) or 0)
            sueldos = 0
            if inc_s and n_emp > 0:
                sueldos = hm.get("E2_1", 0) + max(n_emp - 1, 0) * hm.get("E2_ADIC", 0)
            minimo = math.ceil((base + sueldos) / 100.0) * 100  # redondeo hacia arriba, nunca por debajo de la tabla
            out.append(dict(id=cid, nombre=nom, cond=cond, abono=float(abono or 0), tramo=tramo, tramo_ef=t,
                            base=base, n_emp=n_emp, sueldos=sueldos, inc_s=inc_s, minimo=minimo,
                            debajo=(minimo > 0 and float(abono or 0) < minimo)))
        return out
    A.recomendaciones_honorarios = recomendaciones

    def _aplicar_abono(c, cid, nuevo, mes_actual):
        c.execute("SELECT nombre,abono FROM clientes WHERE id=%s", (cid,))
        r = c.fetchone()
        if not r: return None
        c.execute("UPDATE clientes SET abono=%s WHERE id=%s", (nuevo, cid))
        if mes_actual:
            c.execute("""UPDATE cuentas SET debe=%s WHERE cliente_id=%s AND periodo=%s AND COALESCE(haber,0)=0""",
                      (nuevo, cid, periodo_actual()))
        return r

    @app.route("/honorarios", methods=["GET", "POST"])
    @admin_req
    def honorarios():
        conn = conectar(); c = conn.cursor(); flash = ""; tab = request.args.get("tab", "rec")
        preview_html = ""
        if request.method == "POST":
            acc = request.form.get("accion", "")
            mes_actual = bool(request.form.get("mes_actual"))
            if acc == "guardar_tramo":
                cid = int(request.form.get("cid"))
                c.execute("UPDATE clientes SET tramo_honorario=%s, hon_incluye_sueldos=%s WHERE id=%s",
                          (request.form.get("tramo", "AUTO"), bool(request.form.get("inc_sueldos")), cid))
                conn.commit(); conn.close()
                return redirect("/honorarios?tab=rec#c" + str(cid))
            if acc == "aplicar_minimos":
                ids = [int(x) for x in request.form.getlist("cid")]
                recs = {r["id"]: r for r in recomendaciones(c)}
                n = 0
                for cid in ids:
                    r = recs.get(cid)
                    if r and r["minimo"] > 0:
                        _aplicar_abono(c, cid, r["minimo"], mes_actual)
                        registrar_auditoria("HONORARIO MINIMO", f"Abono {fmt(r['abono'])} → {fmt(r['minimo'])} (tabla CPCESE)", cid, r["nombre"])
                        n += 1
                conn.commit()
                flash = f'<div class="flash fok">✅ Se actualizó el abono de {n} cliente(s) al honorario mínimo.</div>'
                tab = "rec"
            if acc in ("aumento_preview", "aumento_aplicar"):
                tab = "aum"
                try: pct = float((request.form.get("pct") or "0").replace(",", "."))
                except Exception: pct = 0
                cond = request.form.get("cond", "")
                redondeo = int(request.form.get("redondeo", "100") or 100)
                solo_emp = bool(request.form.get("solo_emp"))
                c.execute("""SELECT cl.id,cl.nombre,COALESCE(cl.condicion_fiscal,''),COALESCE(cl.abono,0),
                                    (SELECT COUNT(*) FROM empleados e WHERE e.cliente_id=cl.id AND COALESCE(e.activo,TRUE))
                             FROM clientes cl WHERE COALESCE(cl.activo,TRUE)=TRUE AND COALESCE(cl.abono,0)>0 ORDER BY cl.nombre""")
                lista = []
                for cid, nom, cnd, ab, ne in c.fetchall():
                    if cond and cnd != cond: continue
                    if solo_emp and not ne: continue
                    nuevo = ab * (1 + pct / 100.0)
                    if redondeo > 1: nuevo = round(nuevo / redondeo) * redondeo
                    lista.append((cid, nom, cnd, float(ab), float(nuevo)))
                if acc == "aumento_aplicar":
                    sel = set(int(x) for x in request.form.getlist("cid"))
                    n = 0
                    for cid, nom, cnd, ab, nuevo in lista:
                        if cid in sel:
                            _aplicar_abono(c, cid, nuevo, mes_actual)
                            registrar_auditoria("AUMENTO HONORARIOS", f"{pct}%: {fmt(ab)} → {fmt(nuevo)}", cid, nom)
                            n += 1
                    conn.commit()
                    flash = f'<div class="flash fok">✅ Aumento del {pct:g}% aplicado a {n} cliente(s).</div>'
                else:
                    filas = "".join(
                        f'<tr><td><input type="checkbox" name="cid" value="{cid}" checked class="aum-chk"></td>'
                        f'<td class="nm">{_esc(nom)}</td><td class="mu">{_esc(cnd)}</td><td>{fmt(ab)}</td>'
                        f'<td style="font-weight:700;color:var(--success)">{fmt(nuevo)}</td><td class="mu">+{fmt(nuevo-ab)}</td></tr>'
                        for cid, nom, cnd, ab, nuevo in lista)
                    total_antes = sum(x[3] for x in lista); total_desp = sum(x[4] for x in lista)
                    preview_html = f"""
                    <div class="fcard"><h3>Vista previa: aumento del {pct:g}% · {len(lista)} clientes</h3>
                      <p style="font-size:.84rem;margin-bottom:10px">Facturación mensual: {fmt(total_antes)} → <b>{fmt(total_desp)}</b> (+{fmt(total_desp-total_antes)})</p>
                      <form method="post">
                        <input type="hidden" name="accion" value="aumento_aplicar">
                        <input type="hidden" name="pct" value="{pct}"><input type="hidden" name="cond" value="{_esc(cond)}">
                        <input type="hidden" name="redondeo" value="{redondeo}">{'<input type="hidden" name="solo_emp" value="1">' if solo_emp else ''}
                        <div class="dtable"><table><thead><tr>
                          <th><input type="checkbox" checked onclick="document.querySelectorAll('.aum-chk').forEach(x=>x.checked=this.checked)"></th>
                          <th>Cliente</th><th>Condición</th><th>Abono actual</th><th>Nuevo abono</th><th>Diferencia</th></tr></thead>
                          <tbody>{filas or "<tr><td colspan=6>No hay clientes con ese filtro</td></tr>"}</tbody></table></div>
                        <label style="display:flex;gap:6px;align-items:center;margin:12px 0;font-size:.84rem">
                          <input type="checkbox" name="mes_actual" value="1"> Aplicar también a la deuda de {periodo_actual()} (solo si todavía no pagó)</label>
                        <button class="btn btn-g" onclick="return confirm('¿Aplicar el aumento a los clientes marcados?')">✔ Aplicar aumento</button>
                      </form></div>"""
            if acc == "guardar_tabla":
                for cod, *_ in tabla_hm(c):
                    v = request.form.get("m_" + cod)
                    if v is not None and v.strip():
                        try: c.execute("UPDATE honorarios_minimos SET monto=%s WHERE codigo=%s",
                                       (float(v.replace(".", "").replace(",", ".")), cod))
                        except Exception: pass
                for k in HM_META_DEFAULT:
                    if request.form.get(k) is not None:
                        cfg_set(c, k, request.form.get(k).strip())
                conn.commit(); tab = "tabla"
                registrar_auditoria("HONORARIOS MINIMOS", "Tabla de honorarios mínimos actualizada")
                flash = '<div class="flash fok">✅ Tabla de honorarios mínimos guardada.</div>'
            if acc == "tabla_pct":
                try: p = float((request.form.get("pct_tabla") or "0").replace(",", "."))
                except Exception: p = 0
                if p:
                    c.execute("UPDATE honorarios_minimos SET monto=ROUND((monto*(1+%s/100.0))::numeric,-1)", (p,))
                    conn.commit()
                    registrar_auditoria("HONORARIOS MINIMOS", f"Tabla aumentada {p}%")
                    flash = f'<div class="flash fok">✅ Toda la tabla se actualizó un {p:g}%. Revisá los montos con la nueva resolución.</div>'
                tab = "tabla"

        recs = recomendaciones(c)
        tabla = tabla_hm(c)
        meta = {k: cfg_get(c, k, v) for k, v in HM_META_DEFAULT.items()}
        c.execute("SELECT DISTINCT condicion_fiscal FROM clientes WHERE condicion_fiscal IS NOT NULL ORDER BY 1")
        conds = [r[0] for r in c.fetchall() if r[0]]
        conn.close()

        # ── Recomendaciones ──
        nombres_tramo = dict(TRAMOS)
        hm_desc = {r[0]: r[2] for r in tabla}
        debajo = [r for r in recs if r["debajo"]]
        ver_todos = request.args.get("todos") == "1"
        lista = recs if ver_todos else debajo
        filas = ""
        for r in lista:
            opts = "".join(f'<option value="{k}"{" selected" if k == r["tramo"] else ""}>{v}</option>' for k, v in TRAMOS)
            dif = r["minimo"] - r["abono"]
            pct = (dif / r["abono"] * 100) if r["abono"] > 0 else 0
            detalle = (hm_desc.get(r["tramo_ef"], "Sin tramo") + (f" ({fmt(r['base'])})" if r["base"] else ""))
            if r["sueldos"]:
                detalle += f"<br>+ Sueldos {r['n_emp']} empleado(s): {fmt(r['sueldos'])}"
            estado = (f'<span style="color:var(--danger);font-weight:700">Faltan {fmt(dif)}'
                      f'{f" (+{pct:.0f}%)" if r["abono"] > 0 else ""}</span>' if r["debajo"] else
                      ('<span style="color:var(--success);font-weight:600">✔ En o sobre el mínimo</span>' if r["minimo"] else
                       '<span class="mu">Sin recomendación</span>'))
            filas += f"""<tr id="c{r['id']}">
              <td>{'<input type="checkbox" name="cid" value="'+str(r['id'])+'" form="f-aplicar" class="rec-chk" checked>' if r['debajo'] else ''}</td>
              <td class="nm"><a href="/cuenta/{r['id']}">{_esc(r['nombre'])}</a><br><span class="mu">{_esc(r['cond'])}</span></td>
              <td><form method="post" style="display:flex;flex-direction:column;gap:4px">
                    <input type="hidden" name="accion" value="guardar_tramo"><input type="hidden" name="cid" value="{r['id']}">
                    <select name="tramo" onchange="this.form.submit()" style="font-size:.76rem;padding:3px">{opts}</select>
                    <label style="font-size:.72rem;display:flex;gap:4px;align-items:center">
                      <input type="checkbox" name="inc_sueldos" value="1" {'checked' if r['inc_s'] else ''} onchange="this.form.submit()"> incluir sueldos ({r['n_emp']} emp.)</label>
                  </form></td>
              <td style="font-size:.76rem">{detalle}</td>
              <td>{fmt(r['abono'])}</td>
              <td style="font-weight:700">{fmt(r['minimo']) if r['minimo'] else '—'}</td>
              <td>{estado}</td></tr>"""
        tab_rec = f"""
        <div class="info-box" style="margin-bottom:12px;font-size:.82rem">
          Se compara el abono mensual de cada cliente con la tabla de <b>Honorarios Mínimos Éticos del CPCESE (Res. {_esc(meta['hm_resolucion'])}, vigente desde {_esc(meta['hm_vigencia'])})</b>.
          El mínimo se arma con el tramo impositivo (IVA-IIBB para Responsables Inscriptos, Monotributo según categoría) más la liquidación de sueldos si tiene empleados cargados.
          <b>Revisá el tramo de cada cliente</b> (facturación, Convenio Multilateral, categoría): por defecto se toma el tramo más bajo.
          Recordá que D.1 no incluye la contabilización de las operaciones.</div>
        <div class="stats" style="margin-bottom:14px">
          <div class="scard r"><div class="slabel">Por debajo del mínimo</div><div class="sval">{len(debajo)}</div></div>
          <div class="scard o"><div class="slabel">Diferencia mensual total</div><div class="sval">{fmt(sum(r['minimo']-r['abono'] for r in debajo))}</div></div>
          <div class="scard p"><div class="slabel">Clientes activos</div><div class="sval">{len(recs)}</div></div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center">
          <a href="/honorarios?tab=rec" class="btn btn-xs {'btn-o' if ver_todos else 'btn-p'}">Solo por debajo ({len(debajo)})</a>
          <a href="/honorarios?tab=rec&todos=1" class="btn btn-xs {'btn-p' if ver_todos else 'btn-o'}">Todos los clientes</a>
        </div>
        <form id="f-aplicar" method="post" onsubmit="return confirm('¿Actualizar el abono de los clientes marcados al honorario mínimo?')">
          <input type="hidden" name="accion" value="aplicar_minimos"></form>
        <div class="fcard"><div class="dtable"><table>
          <thead><tr><th><input type="checkbox" checked onclick="document.querySelectorAll('.rec-chk').forEach(x=>x.checked=this.checked)"></th>
            <th>Cliente</th><th>Tramo</th><th>Cálculo según tabla</th><th>Abono actual</th><th>Mínimo ético</th><th>Recomendación</th></tr></thead>
          <tbody>{filas or "<tr><td colspan=7 style='text-align:center;padding:20px;color:var(--muted)'>🎉 Ningún cliente está por debajo del mínimo</td></tr>"}</tbody>
        </table></div>
        {f'''<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px">
          <label style="font-size:.84rem;display:flex;gap:6px;align-items:center"><input type="checkbox" name="mes_actual" value="1" form="f-aplicar">
            Aplicar también a la deuda de {periodo_actual()} (solo si todavía no pagó)</label>
          <button class="btn btn-g" form="f-aplicar">✔ Actualizar marcados al mínimo</button></div>''' if debajo else ''}
        </div>"""

        # ── Aumento por % ──
        cond_opts = '<option value="">Todas las condiciones</option>' + "".join(f'<option value="{_esc(x)}">{_esc(x)}</option>' for x in conds)
        tab_aum = f"""
        <div class="fcard"><h3>Aumento masivo de honorarios</h3>
          <form method="post"><input type="hidden" name="accion" value="aumento_preview">
            <div class="fgrid">
              <div class="fg"><label>Porcentaje de aumento %</label><input name="pct" type="number" step="0.01" required placeholder="Ej: 15"></div>
              <div class="fg"><label>Clientes</label><select name="cond">{cond_opts}</select></div>
              <div class="fg"><label>Redondear a</label><select name="redondeo">
                <option value="100">$100</option><option value="500">$500</option><option value="1000" selected>$1.000</option><option value="1">Sin redondeo</option></select></div>
              <div class="fg"><label>&nbsp;</label><label style="display:flex;gap:6px;align-items:center;font-size:.84rem">
                <input type="checkbox" name="solo_emp" value="1"> Solo clientes con empleados</label></div>
            </div>
            <button class="btn btn-p">👁 Ver vista previa</button>
            <p style="font-size:.78rem;color:var(--muted);margin-top:8px">Primero ves cómo queda cada cliente; nada se modifica hasta que confirmes.</p>
          </form></div>{preview_html}"""

        # ── Tabla editable ──
        filas_t = ""; grupo_ant = None
        for cod, grp, desc, monto, uni in tabla:
            if grp != grupo_ant:
                filas_t += f'<tr><td colspan=4 style="background:var(--bg);font-weight:700;color:var(--primary)">{_esc(grp)}</td></tr>'
                grupo_ant = grp
            filas_t += (f'<tr><td class="mu">{_esc(cod_vis(cod))}</td><td>{_esc(desc)}</td><td class="mu">{_esc(uni or "")}</td>'
                        f'<td><input name="m_{cod}" value="{monto:.0f}" style="width:120px;text-align:right"></td></tr>')
        tab_tabla = f"""
        <div class="fcard"><h3>Tabla de honorarios mínimos éticos (CPCESE)</h3>
          <form method="post"><input type="hidden" name="accion" value="guardar_tabla">
            <div class="fgrid" style="margin-bottom:10px">
              <div class="fg"><label>Resolución</label><input name="hm_resolucion" value="{_esc(meta['hm_resolucion'])}"></div>
              <div class="fg"><label>Vigente desde</label><input name="hm_vigencia" value="{_esc(meta['hm_vigencia'])}"></div>
              <div class="fg" style="grid-column:span 2"><label>Link al PDF del Consejo</label><input name="hm_pdf" value="{_esc(meta['hm_pdf'])}"></div>
            </div>
            <div class="dtable"><table><thead><tr><th>Cód.</th><th>Tarea</th><th>Unidad</th><th>Mínimo $</th></tr></thead>
              <tbody>{filas_t}</tbody></table></div>
            <button class="btn btn-g" style="margin-top:12px">💾 Guardar tabla</button>
          </form>
          <form method="post" style="display:flex;gap:8px;align-items:end;margin-top:16px;flex-wrap:wrap"
                onsubmit="return confirm('¿Aumentar TODOS los montos de la tabla en ese porcentaje?')">
            <input type="hidden" name="accion" value="tabla_pct">
            <div class="fg" style="margin:0"><label>Actualizar toda la tabla un %</label><input name="pct_tabla" type="number" step="0.01" placeholder="Ej: 20"></div>
            <button class="btn btn-o btn-sm">Aplicar % a la tabla</button>
          </form>
          <p style="font-size:.78rem;color:var(--muted);margin-top:10px">Cuando el Consejo publique una nueva resolución, actualizá los montos acá
            (o pedile a Claude que los cargue) y las recomendaciones se recalculan solas.</p>
        </div>"""

        def tb(k, label):
            return f'<button class="tab{" on" if tab == k else ""}" onclick="showTab(\'th-{k}\',this)">{label}</button>'
        body = f"""
        <h1 class="page-title">💲 Honorarios</h1>
        <p class="page-sub">Recomendaciones según la tabla del Consejo y actualización de abonos ·
          <a href="{_esc(meta['hm_pdf'])}" target="_blank">Ver PDF Res. {_esc(meta['hm_resolucion'])}</a></p>
        {flash}
        <div class="tabs" style="margin-bottom:14px">{tb('rec','📋 Recomendaciones por cliente')}{tb('aum','📈 Aumento por %')}{tb('tabla','📑 Tabla del Consejo')}</div>
        <div id="th-rec" class="tabpanel{' on' if tab=='rec' else ''}">{tab_rec}</div>
        <div id="th-aum" class="tabpanel{' on' if tab=='aum' else ''}">{tab_aum}</div>
        <div id="th-tabla" class="tabpanel{' on' if tab=='tabla' else ''}">{tab_tabla}</div>
        <script>function showTab(id,btn){{document.querySelectorAll('.tabpanel').forEach(p=>p.classList.remove('on'));
          document.querySelectorAll('.tabs .tab').forEach(b=>b.classList.remove('on'));
          document.getElementById(id).classList.add('on');btn.classList.add('on');}}</script>"""
        return page("Honorarios", body, "Clientes")

    def html_honorarios_novedades():
        """Contenido de la solapa 'Honorarios mínimos' en Novedades."""
        conn = conectar(); c = conn.cursor()
        tabla = tabla_hm(c)
        meta = {k: cfg_get(c, k, v) for k, v in HM_META_DEFAULT.items()}
        n_debajo = 0
        if session.get("rol") == "admin":
            try: n_debajo = sum(1 for r in recomendaciones(c) if r["debajo"])
            except Exception: n_debajo = 0
        conn.close()
        grupos = {}
        for cod, grp, desc, monto, uni in tabla:
            grupos.setdefault(grp, []).append((cod, desc, monto, uni))
        cards = ""
        for grp, items in grupos.items():
            filas = "".join(
                f'<div style="display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--border);font-size:.82rem">'
                f'<span><span class="mu">{_esc(cod_vis(cod))}</span> {_esc(desc)} <span class="mu">· {_esc(uni or "")}</span></span>'
                f'<b style="white-space:nowrap">{fmt(monto)}</b></div>' for cod, desc, monto, uni in items)
            cards += f'<div class="fcard" style="margin-bottom:0"><h3>{_esc(grp)}</h3>{filas}</div>'
        admin_box = ""
        if session.get("rol") == "admin":
            admin_box = (f'<div class="{"warn-box" if n_debajo else "info-box"}" style="margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">'
                         f'<span>{"⚠ <b>" + str(n_debajo) + " cliente(s)</b> tienen un abono por debajo del honorario mínimo ético." if n_debajo else "✔ Todos los clientes con tramo asignado están en o sobre el mínimo."}</span>'
                         f'<a href="/honorarios" class="btn btn-a btn-sm">Ver recomendaciones</a></div>')
        return (f'<div class="fcard" style="margin-bottom:14px"><h3>Honorarios Mínimos Éticos — CPCE Santiago del Estero</h3>'
                f'<p style="font-size:.86rem">Resolución N° <b>{_esc(meta["hm_resolucion"])}</b> · vigentes a partir del <b>{_esc(meta["hm_vigencia"])}</b></p>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">'
                f'<a href="{_esc(meta["hm_pdf"])}" target="_blank" class="btn btn-a btn-sm">📄 Ver PDF oficial</a>'
                f'<a href="https://cpcese.org.ar/matriculados/honorarios-minimos-eticos" target="_blank" class="btn btn-o btn-sm">Página del Consejo</a></div></div>'
                + admin_box +
                f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px">{cards}</div>')
    A.html_honorarios_novedades = html_honorarios_novedades

    # ══════════════════════════════════════════════════════════════════════════
    #  4) DEUDORES + RECORDATORIOS POR WHATSAPP
    # ══════════════════════════════════════════════════════════════════════════
    def deudas_v2():
        es_admin = session.get("rol") == "admin"
        conn = conectar(); c = conn.cursor(); flash = ""
        if request.method == "POST" and es_admin and request.form.get("accion") == "guardar_msg":
            cfg_set(c, "msg_recordatorio", request.form.get("msg", "").strip() or MSG_RECORDATORIO_DEFAULT)
            conn.commit(); flash = '<div class="flash fok">✅ Mensaje de recordatorio guardado.</div>'
        plantilla = cfg_get(c, "msg_recordatorio", MSG_RECORDATORIO_DEFAULT)
        try: min_saldo = float(request.args.get("min", "0") or 0)
        except Exception: min_saldo = 0
        solo_pend = request.args.get("pend") == "1"
        mes = periodo_actual()
        c.execute("""SELECT cl.id,cl.nombre,cl.telefono,SUM(cu.debe-cu.haber) saldo
                     FROM cuentas cu JOIN clientes cl ON cl.id=cu.cliente_id
                     GROUP BY cl.id,cl.nombre,cl.telefono
                     HAVING SUM(cu.debe-cu.haber)>0.5
                     ORDER BY saldo DESC""")
        data = c.fetchall()
        c.execute("""SELECT cliente_id,periodo FROM cuentas WHERE COALESCE(debe,0)-COALESCE(haber,0)>0.5
                     ORDER BY cliente_id, SUBSTRING(periodo,4,4), SUBSTRING(periodo,1,2)""")
        pers = {}
        for cid, per in c.fetchall(): pers.setdefault(cid, []).append(per)
        c.execute("""SELECT DISTINCT ON (cliente_id) cliente_id,fecha,periodo_envio,usuario
                     FROM recordatorios_deuda ORDER BY cliente_id, id DESC""")
        ult = {r[0]: (r[1], r[2], r[3]) for r in c.fetchall()}
        conn.close()
        total = sum(r[3] for r in data)
        cards = ""; cola = []; n_pend_mes = 0
        for cid, nombre, tel_enc, saldo in data:
            if saldo < min_saldo: continue
            u = ult.get(cid)
            enviado_mes = bool(u and u[1] == mes)
            if not enviado_mes: n_pend_mes += 1
            if solo_pend and enviado_mes: continue
            num = _wa_num(dec(tel_enc) if tel_enc else "")
            lp = pers.get(cid, [])
            periodos_txt = ("períodos " + ", ".join(lp[-6:]) + (" y anteriores" if len(lp) > 6 else "")) if lp else "saldo anterior"
            try:
                msg = plantilla.format(nombre=nombre, saldo=fmt(saldo), periodos=periodos_txt)
            except Exception:
                msg = MSG_RECORDATORIO_DEFAULT.format(nombre=nombre, saldo=fmt(saldo), periodos=periodos_txt)
            link = f"https://wa.me/{num}?text={urllib.parse.quote(msg)}" if num else ""
            if link and not enviado_mes: cola.append({"id": cid, "link": link, "nombre": nombre})
            ult_txt = (f'<span style="color:var(--success);font-size:.74rem">✔ Recordado {_esc(u[0])} ({_esc(u[2] or "")})</span>' if enviado_mes
                       else (f'<span class="mu" style="font-size:.74rem">Último recordatorio: {_esc(u[0])}</span>' if u
                             else '<span class="mu" style="font-size:.74rem">Sin recordatorios</span>'))
            btn = (f'<a href="{link}" target="_blank" class="btn btn-xs btn-wa" onclick="marcar({cid},this)">📱 Recordar</a>' if num
                   else '<span class="mu" style="font-size:.74rem">Sin teléfono</span>')
            cards += (f'<div class="dcard" id="d{cid}"><div><span class="dname">{_esc(nombre)}</span><br>'
                      f'<span class="mu" style="font-size:.74rem">{_esc(periodos_txt)}</span><br>{ult_txt}</div>'
                      f'<div class="damt">{fmt(saldo)}</div>'
                      f'<div style="display:flex;gap:6px;flex-wrap:wrap"><a href="/cuenta/{cid}" class="btn btn-xs btn-p">Ver cuenta</a>{btn}</div></div>')
        editor = ""
        if es_admin:
            editor = f"""<details class="fcard" style="margin-bottom:14px"><summary style="cursor:pointer;font-weight:600">✏️ Editar mensaje de recordatorio</summary>
              <form method="post" style="margin-top:10px"><input type="hidden" name="accion" value="guardar_msg">
                <textarea name="msg" rows="4" style="width:100%">{_esc(plantilla)}</textarea>
                <p style="font-size:.76rem;color:var(--muted);margin:6px 0">Podés usar {{nombre}}, {{saldo}} y {{periodos}}: se reemplazan solos con los datos de cada cliente.</p>
                <button class="btn btn-g btn-sm">Guardar mensaje</button></form></details>"""
        body = f"""
        <h1 class="page-title">Deudores</h1>
        <p class="page-sub">{len(data)} clientes con saldo pendiente · Total: {fmt(total)}</p>{flash}
        <div class="fcard" style="margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
            <div><b>📱 Recordatorios de {mes}</b><br><span class="mu" style="font-size:.82rem">
              {n_pend_mes} deudor(es) todavía no recibieron recordatorio este mes</span></div>
            {f'<button class="btn btn-wa" id="btn-sig" onclick="siguiente()">📱 Enviar al siguiente (1 de {len(cola)})</button>' if cola else '<span class="mu">✔ No hay recordatorios pendientes con teléfono</span>'}
          </div>
          <form method="get" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px;font-size:.84rem">
            <label>Saldo mínimo $ <input name="min" type="number" value="{min_saldo:.0f}" style="width:110px"></label>
            <label style="display:flex;gap:5px;align-items:center"><input type="checkbox" name="pend" value="1" {'checked' if solo_pend else ''}> Solo sin recordatorio este mes</label>
            <button class="btn btn-o btn-xs">Filtrar</button></form>
        </div>
        {editor}
        {cards or '<div class="info-box">Sin deudores 🎉</div>'}
        <script>
        var cola={json.dumps(cola)}, idx=0;
        function marcar(cid,el){{
          fetch('/deudas/recordatorio/'+cid,{{method:'POST'}}).catch(function(){{}});
          var d=document.getElementById('d'+cid); if(d) d.style.opacity='.55';
          if(el) el.textContent='✔ Enviado';
        }}
        function siguiente(){{
          if(idx>=cola.length) return;
          var it=cola[idx]; window.open(it.link,'_blank'); marcar(it.id,null); idx++;
          var b=document.getElementById('btn-sig');
          if(idx>=cola.length){{ b.textContent='✔ Listo, se enviaron todos'; b.disabled=true; }}
          else b.textContent='📱 Enviar al siguiente ('+(idx+1)+' de '+cola.length+') · '+cola[idx].nombre;
        }}
        </script>"""
        return page("Deudores", body, "Deudores")
    app.view_functions["deudas"] = login_req(deudas_v2)

    @app.route("/deudas/recordatorio/<int:cid>", methods=["POST"])
    @login_req
    def registrar_recordatorio(cid):
        conn = conectar(); c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(debe-haber),0) FROM cuentas WHERE cliente_id=%s", (cid,))
        saldo = c.fetchone()[0]
        c.execute("INSERT INTO recordatorios_deuda(cliente_id,fecha,periodo_envio,usuario,saldo) VALUES(%s,%s,%s,%s,%s)",
                  (cid, now_ar(), periodo_actual(), session.get("display", ""), saldo))
        conn.commit(); conn.close()
        return ("", 204)
