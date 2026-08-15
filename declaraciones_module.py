def register_declaraciones(app):
    from flask import request, redirect, session
    from app import conectar, fmt, now_ar, registrar_auditoria, login_req, page, dec

    def _init_db():
        conn = conectar(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS declaraciones_control(
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
            modulo TEXT NOT NULL,
            anio INTEGER NOT NULL,
            estado TEXT DEFAULT 'falta',
            observaciones TEXT DEFAULT '',
            honorario_pagado BOOLEAN DEFAULT FALSE,
            monto_honorario REAL DEFAULT 0,
            fecha_actualizacion TEXT,
            usuario TEXT,
            UNIQUE(cliente_id, modulo, anio))""")
        conn.commit(); c.close(); conn.close()

    _init_db()

    ESTADOS = [("presentado", "Presentado"), ("falta", "Falta de Presentacion"), ("rectificar", "Rectificar Presentacion")]
    ESTADO_LBL = dict(ESTADOS)
    ESTADO_COLOR = {"presentado": "#1D9E75", "falta": "#C0392B", "rectificar": "#E67E22"}

    def _badge_estado(estado):
        col = ESTADO_COLOR.get(estado, "#888")
        lbl = ESTADO_LBL.get(estado, estado)
        return f'<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:{col}22;color:{col};font-weight:700">{lbl}</span>'

    def _fragmento_modulo(modulo_key, titulo, subt, filtro_sql, con_honorario, redir_default, form_id):
        """Arma el HTML del modulo (tarjetas por cliente + modal de alta/edicion), sin el wrapper de pagina.
        Se usa tanto para la pagina standalone como para la solapa embebida en Reportes."""
        conn = conectar(); c = conn.cursor()
        c.execute(f"SELECT id,nombre,cuit FROM clientes WHERE (activo IS NOT FALSE) AND ({filtro_sql}) ORDER BY nombre")
        clientes = c.fetchall()
        c.execute("""SELECT id,cliente_id,anio,estado,observaciones,honorario_pagado,monto_honorario
                     FROM declaraciones_control WHERE modulo=%s ORDER BY anio DESC""", (modulo_key,))
        filas_db = c.fetchall()
        conn.close()

        por_cliente = {}
        for did, cid, anio, estado, obs, hon_pag, monto in filas_db:
            por_cliente.setdefault(cid, []).append((did, anio, estado, obs, hon_pag, monto))

        estado_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in ESTADOS)
        n_total_falta = 0
        bloques = ""
        for cid, nombre, cuit_enc in clientes:
            cuit_d = dec(cuit_enc) if cuit_enc else ""
            periodos = sorted(por_cliente.get(cid, []), key=lambda p: -p[1])
            n_falta_cli = sum(1 for p in periodos if p[2] != "presentado")
            n_total_falta += n_falta_cli
            filas_per = ""
            for did, anio, estado, obs, hon_pag, monto in periodos:
                hon_td = ""
                if con_honorario:
                    hon_txt = "Pagado" if hon_pag else "Pendiente"
                    hon_col = "#1D9E75" if hon_pag else "#C0392B"
                    monto_txt = f" · {fmt(monto)}" if monto else ""
                    hon_td = f'<td><span style="font-size:.68rem;color:{hon_col};font-weight:700">{hon_txt}{monto_txt}</span></td>'
                obs_attr = (obs or "").replace(chr(34), "&quot;")
                filas_per += f'''<tr>
                    <td>{anio}</td>
                    <td>{_badge_estado(estado)}</td>
                    {hon_td}
                    <td class="mu" style="max-width:220px">{(obs or "")[:70]}</td>
                    <td style="white-space:nowrap">
                        <button type="button" class="btn btn-xs btn-o declEditBtn{form_id}"
                            data-did="{did}" data-cid="{cid}" data-nombre="{nombre}" data-anio="{anio}"
                            data-estado="{estado}" data-obs="{obs_attr}"
                            data-honpag="{1 if hon_pag else 0}" data-monto="{monto or 0}">Editar</button>
                        <form method="post" action="/declaracion/borrar/{did}" style="display:inline"
                            onsubmit="return confirm('Borrar este periodo cargado?')">
                            <input type="hidden" name="redir" value="{redir_default}">
                            <button class="btn btn-xs btn-r" title="Borrar periodo">🗑</button>
                        </form>
                    </td></tr>'''
            colspan = 5 if con_honorario else 4
            bloques += f'''<div class="fcard" style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px">
                    <div><span style="font-weight:600;color:var(--primary)">{nombre}</span>
                        <span class="mu" style="font-size:.78rem"> · {cuit_d or "---"}</span>
                        {f'<span style="font-size:.68rem;color:var(--danger);font-weight:700;margin-left:8px">{n_falta_cli} pendiente(s)</span>' if n_falta_cli else '<span style="font-size:.68rem;color:var(--success);font-weight:700;margin-left:8px">Al dia</span>'}
                    </div>
                    <button type="button" class="btn btn-p btn-sm declAddBtn{form_id}" data-cid="{cid}" data-nombre="{nombre}">+ Agregar Año</button>
                </div>
                <div class="dtable"><table><thead><tr><th>Año</th><th>Estado</th>{"<th>Honorario</th>" if con_honorario else ""}<th>Observaciones</th><th></th></tr></thead>
                <tbody>{filas_per or f"<tr><td colspan={colspan} style='color:var(--muted);text-align:center;padding:10px'>Sin periodos cargados</td></tr>"}</tbody></table></div>
            </div>'''

        hon_campo = ""
        if con_honorario:
            hon_campo = f'''
                <div style="display:flex;align-items:center;gap:8px;margin:10px 0">
                    <input type="checkbox" name="honorario_pagado" value="1" id="decl_honpag_{form_id}" style="width:auto">
                    <label style="font-size:.84rem;cursor:pointer" for="decl_honpag_{form_id}">Honorario de la presentación pagado</label>
                </div>
                <div class="fg"><label>Monto del honorario (opcional)</label><input type="number" step="0.01" name="monto_honorario" id="decl_monto_{form_id}"></div>'''

        body = f'''
        <p class="page-sub" style="margin-bottom:10px">{subt}{" &middot; " + str(n_total_falta) + " periodo(s) pendiente(s) en total" if n_total_falta else ""}</p>
        {bloques or "<div class='info-box'>No hay clientes marcados para este modulo todavia. Marcalos desde la ficha de cada cliente en /clientes.</div>"}
        <div class="mo" id="mdecl_{form_id}"><div class="modal">
            <h3>{titulo}</h3>
            <p class="msub" id="mdecl_nombre_lbl_{form_id}"></p>
            <form method="post" action="/declaracion/guardar">
                <input type="hidden" name="modulo" value="{modulo_key}">
                <input type="hidden" name="redir" value="{redir_default}">
                <input type="hidden" name="cliente_id" id="mdecl_cid_{form_id}">
                <div class="fgrid">
                    <div class="fg"><label>Año</label><input type="number" name="anio" id="mdecl_anio_{form_id}" placeholder="2025" required></div>
                    <div class="fg"><label>Estado</label><select name="estado" id="mdecl_estado_{form_id}">{estado_opts}</select></div>
                </div>
                {hon_campo}
                <div class="fg" style="margin:10px 0"><label>Observaciones</label><textarea name="observaciones" id="mdecl_obs_{form_id}" rows="3" placeholder="Notas sobre esta presentacion..."></textarea></div>
                <div class="mact">
                    <button type="button" class="btn btn-o" onclick="document.getElementById('mdecl_{form_id}').classList.remove('on')">Cancelar</button>
                    <button type="submit" class="btn btn-p">Guardar</button>
                </div>
            </form>
        </div></div>
        <script>
        (function(){{
        function _declAbrir(cid,nombre,anio,estado,obs,honpag,monto){{
            document.getElementById('mdecl_cid_{form_id}').value=cid;
            document.getElementById('mdecl_nombre_lbl_{form_id}').textContent=nombre;
            document.getElementById('mdecl_anio_{form_id}').value=anio||'';
            document.getElementById('mdecl_estado_{form_id}').value=estado||'falta';
            document.getElementById('mdecl_obs_{form_id}').value=obs||'';
            var hp=document.getElementById('decl_honpag_{form_id}'); if(hp) hp.checked = honpag==='1';
            var mo=document.getElementById('decl_monto_{form_id}'); if(mo) mo.value = monto||'';
            document.getElementById('mdecl_{form_id}').classList.add('on');
        }}
        document.addEventListener('click',function(e){{
            var addBtn=e.target.closest('.declAddBtn{form_id}');
            if(addBtn){{ _declAbrir(addBtn.dataset.cid,addBtn.dataset.nombre,'','falta','','0','0'); return; }}
            var editBtn=e.target.closest('.declEditBtn{form_id}');
            if(editBtn){{ _declAbrir(editBtn.dataset.cid,editBtn.dataset.nombre,editBtn.dataset.anio,editBtn.dataset.estado,editBtn.dataset.obs,editBtn.dataset.honpag,editBtn.dataset.monto); return; }}
        }});
        document.querySelectorAll('.mo').forEach(m=>m.addEventListener('click',e=>{{if(e.target===m)m.classList.remove('on')}}));
        }})();
        </script>
        '''
        return body

    _MODULOS = {
        "ganancias": dict(modulo_key="ganancias", titulo="Control de Ganancias",
            subt="Clientes inscriptos en Ganancias - DJ anual pendiente, presentada y honorario de la presentacion",
            filtro_sql="inscripto_ganancias=TRUE", con_honorario=True, ruta="ganancias",
            nav_label="Ganancias", form_id="gan", tab_id="t8"),
        "bienes_personales": dict(modulo_key="bienes_personales", titulo="Control de Bienes Personales",
            subt="Clientes inscriptos en Bienes Personales - DJ anual pendiente y presentada",
            filtro_sql="inscripto_bienes_personales=TRUE", con_honorario=False, ruta="bienes-personales",
            nav_label="Bienes Personales", form_id="bp", tab_id="t9"),
        "part_societarias": dict(modulo_key="part_societarias", titulo="Participaciones Societarias",
            subt="Solo sociedades - DJ de participaciones societarias por año",
            filtro_sql="es_sociedad=TRUE", con_honorario=False, ruta="participaciones-societarias",
            nav_label="Part. Societarias", form_id="ps", tab_id="t10"),
        "pub": dict(modulo_key="pub", titulo="PUB - Presentación Única de Balances",
            subt="Solo sociedades - control de presentacion de balances por año",
            filtro_sql="es_sociedad=TRUE", con_honorario=False, ruta="pub",
            nav_label="PUB", form_id="pub", tab_id="t11"),
    }

    def _fragmento(clave, redir_default):
        m = _MODULOS[clave]
        return _fragmento_modulo(m["modulo_key"], m["titulo"], m["subt"], m["filtro_sql"],
                                  m["con_honorario"], redir_default, m["form_id"])

    # Fragmentos para embeber como solapas dentro de /reportes
    app.frag_ganancias = lambda: _fragmento("ganancias", "/reportes?tab=t8")
    app.frag_bienes_personales = lambda: _fragmento("bienes_personales", "/reportes?tab=t9")
    app.frag_part_societarias = lambda: _fragmento("part_societarias", "/reportes?tab=t10")
    app.frag_pub = lambda: _fragmento("pub", "/reportes?tab=t11")

    def _pagina_standalone(clave):
        m = _MODULOS[clave]
        volver = f'<a href="/reportes?tab={m["tab_id"]}" class="btn btn-o btn-sm" style="margin-bottom:16px">&larr; Volver a Reportes</a>'
        titulo_html = f'<p class="page-title">{m["titulo"]}</p>'
        frag = _fragmento(clave, f'/{m["ruta"]}')
        return page(m["titulo"], volver + titulo_html + frag, m["nav_label"])

    # ── Paginas standalone (ya no estan en el menu superior, pero siguen accesibles por URL
    #    y tienen boton Volver a Reportes) ──
    @app.route("/ganancias", methods=["GET"])
    @login_req
    def ganancias_vista():
        return _pagina_standalone("ganancias")

    @app.route("/bienes-personales", methods=["GET"])
    @login_req
    def bienes_personales_vista():
        return _pagina_standalone("bienes_personales")

    @app.route("/participaciones-societarias", methods=["GET"])
    @login_req
    def part_societarias_vista():
        return _pagina_standalone("part_societarias")

    @app.route("/pub", methods=["GET"])
    @login_req
    def pub_vista():
        return _pagina_standalone("pub")

    # ── Guardar / borrar periodo (compartido por los 4 modulos) ──
    @app.route("/declaracion/guardar", methods=["POST"])
    @login_req
    def declaracion_guardar():
        f = request.form
        modulo = f.get("modulo", "").strip()
        cliente_id = f.get("cliente_id")
        redir = f.get("redir", "/reportes")
        try:
            anio = int(f.get("anio"))
        except (TypeError, ValueError):
            return redirect(redir)
        estado = f.get("estado", "falta")
        if estado not in ESTADO_LBL: estado = "falta"
        observaciones = f.get("observaciones", "").strip()
        honorario_pagado = f.get("honorario_pagado", "0") == "1"
        try:
            monto_honorario = float(f.get("monto_honorario", 0) or 0)
        except ValueError:
            monto_honorario = 0
        if not modulo or not cliente_id:
            return redirect(redir)
        conn = conectar(); c = conn.cursor()
        c.execute("""INSERT INTO declaraciones_control(cliente_id,modulo,anio,estado,observaciones,
                     honorario_pagado,monto_honorario,fecha_actualizacion,usuario)
                     VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     ON CONFLICT(cliente_id,modulo,anio) DO UPDATE SET
                     estado=EXCLUDED.estado, observaciones=EXCLUDED.observaciones,
                     honorario_pagado=EXCLUDED.honorario_pagado, monto_honorario=EXCLUDED.monto_honorario,
                     fecha_actualizacion=EXCLUDED.fecha_actualizacion, usuario=EXCLUDED.usuario""",
                  (cliente_id, modulo, anio, estado, observaciones, honorario_pagado, monto_honorario,
                   now_ar(), session.get("display", session.get("user", "?"))))
        conn.commit(); conn.close()
        registrar_auditoria("DECLARACION_CONTROL", f"{modulo} {anio} -> {estado}", cliente_id)
        return redirect(redir)

    @app.route("/declaracion/borrar/<int:did>", methods=["POST"])
    @login_req
    def declaracion_borrar(did):
        redir = request.form.get("redir", "/reportes")
        conn = conectar(); c = conn.cursor()
        c.execute("DELETE FROM declaraciones_control WHERE id=%s", (did,))
        conn.commit(); conn.close()
        registrar_auditoria("DECLARACION_CONTROL", f"Borro periodo id {did}")
        return redirect(redir)
