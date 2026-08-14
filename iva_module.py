def register_iva(app):
    from flask import request, redirect, session
    from app import conectar, fmt, now_ar, now_ar_dt, registrar_auditoria, login_req, page

    def _init_iva_db():
        conn = conectar(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS iva_control(
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            ventas REAL DEFAULT 0,
            notas_credito_emitidas REAL DEFAULT 0,
            compras REAL DEFAULT 0,
            notas_credito_recibidas REAL DEFAULT 0,
            saldo_anterior REAL DEFAULT 0,
            saldo_libre_disponibilidad REAL DEFAULT 0,
            retenciones_percepciones REAL DEFAULT 0,
            neto_ventas_comprobantes REAL DEFAULT 0,
            neto_liquidaciones REAL DEFAULT 0,
            actividad TEXT DEFAULT '',
            alicuota_iibb REAL DEFAULT 3,
            pagos_cuenta_iibb REAL DEFAULT 0,
            retenciones_iibb REAL DEFAULT 0,
            fecha_actualizacion TEXT,
            usuario TEXT,
            UNIQUE(cliente_id,mes,anio))""")
        conn.commit(); c.close(); conn.close()

    _init_iva_db()

    def _periodo(req):
        hoy = now_ar_dt()
        try: mes = int(req.args.get("mes", hoy.month))
        except: mes = hoy.month
        try: anio = int(req.args.get("anio", hoy.year))
        except: anio = hoy.year
        if mes < 1: mes = 12; anio -= 1
        if mes > 12: mes = 1; anio += 1
        return mes, anio

    MESES_NOM = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    @app.route("/iva", methods=["GET"])
    @login_req
    def iva_control_vista():
        mes, anio = _periodo(request)
        pm, pa = (12, anio-1) if mes == 1 else (mes-1, anio)
        nm, na = (1, anio+1) if mes == 12 else (mes+1, anio)
        conn = conectar(); c = conn.cursor()
        c.execute("""SELECT id,nombre FROM clientes
            WHERE (activo IS NOT FALSE) AND (condicion_fiscal='Responsable Inscripto' OR responsable_inscripto=TRUE)
            ORDER BY nombre""")
        clientes = c.fetchall()
        c.execute("""SELECT cliente_id,ventas,notas_credito_emitidas,compras,notas_credito_recibidas,
            saldo_anterior,saldo_libre_disponibilidad,retenciones_percepciones,
            neto_ventas_comprobantes,neto_liquidaciones,actividad,alicuota_iibb,
            pagos_cuenta_iibb,retenciones_iibb
            FROM iva_control WHERE mes=%s AND anio=%s""",(mes,anio))
        datos = {r[0]: r for r in c.fetchall()}
        conn.close()
        filas = ""
        for cid, nombre in clientes:
            d = datos.get(cid)
            if d:
                (_,ventas,ncred_e,compras,ncred_r,saldo_ant,saldo_libre,ret_perc,
                 neto_ventas,neto_liq,actividad,alicuota,pagos_cta,ret_iibb) = d
            else:
                ventas=ncred_e=compras=ncred_r=saldo_ant=saldo_libre=ret_perc=0
                neto_ventas=neto_liq=pagos_cta=ret_iibb=0
                actividad=""; alicuota=3
            deb_fiscal = (ventas or 0) - (ncred_e or 0)
            cred_fiscal = (compras or 0) - (ncred_r or 0)
            resultado = deb_fiscal - cred_fiscal - (saldo_ant or 0) - (saldo_libre or 0) - (ret_perc or 0)
            iibb_est = ((neto_ventas or 0) + (neto_liq or 0)) * ((alicuota or 0)/100)
            iibb_neto = iibb_est - (pagos_cta or 0) - (ret_iibb or 0)
            if resultado > 0:
                bad_iva = f'<span class="badge bp">Saldo a favor {fmt(resultado)}</span>'
            elif resultado < 0:
                bad_iva = f'<span class="badge bd">IVA a pagar {fmt(abs(resultado))}</span>'
            else:
                bad_iva = '<span class="badge bpar">Sin saldo</span>'
            if iibb_neto > 0:
                bad_iibb = f'<span class="badge bd">A pagar {fmt(iibb_neto)}</span>'
            else:
                bad_iibb = f'<span class="badge bp">{fmt(iibb_neto)}</span>'
            filas += f'''<tr>
                <td class="nm">{nombre}</td>
                <td>{fmt(ventas)}</td>
                <td>{fmt(compras)}</td>
                <td>{bad_iva}</td>
                <td>{bad_iibb}</td>
                <td><button class="btn btn-o btn-sm ivaBtn"
                    data-cid="{cid}" data-nombre="{nombre}"
                    data-ventas="{ventas or 0}" data-ncrede="{ncred_e or 0}"
                    data-compras="{compras or 0}" data-ncredr="{ncred_r or 0}"
                    data-saldoant="{saldo_ant or 0}" data-saldolibre="{saldo_libre or 0}"
                    data-retperc="{ret_perc or 0}" data-netoventas="{neto_ventas or 0}"
                    data-netoliq="{neto_liq or 0}" data-actividad="{actividad or ''}"
                    data-alicuota="{alicuota if alicuota is not None else 3}"
                    data-pagoscta="{pagos_cta or 0}" data-retiibb="{ret_iibb or 0}">Cargar</button></td>
                </tr>'''
        body = f'''
        <p class="page-title">Control de IVA e Ingresos Brutos</p>
        <p class="page-sub">Responsables Inscriptos - calculo mensual de IVA e IIBB estimado</p>
        <div class="arow">
            <a class="btn btn-o btn-sm" href="/iva?mes={pm}&anio={pa}">&larr; Anterior</a>
            <span class="period">{MESES_NOM[mes]} {anio}</span>
            <a class="btn btn-o btn-sm" href="/iva?mes={nm}&anio={na}">Siguiente &rarr;</a>
        </div>
        <div class="dtable"><table>
            <thead><tr><th>Cliente</th><th>Ventas</th><th>Compras</th><th>Resultado IVA</th><th>IIBB estimado</th><th></th></tr></thead>
            <tbody>{filas}</tbody>
        </table></div>
        <div class="mo" id="miva"><div class="modal">
            <h3>Control de IVA / IIBB</h3>
            <p class="msub" id="miva_nombre_lbl"></p>
            <form method="post" action="/iva/guardar">
                <input type="hidden" name="cliente_id" id="miva_cid">
                <input type="hidden" name="mes" value="{mes}">
                <input type="hidden" name="anio" value="{anio}">
                <h3 style="font-size:.95rem">IVA</h3>
                <div class="fgrid">
                    <div class="fg"><label>Ventas</label><input type="number" step="0.01" name="ventas" id="f_ventas"></div>
                    <div class="fg"><label>Notas Cred. Emitidas</label><input type="number" step="0.01" name="notas_credito_emitidas" id="f_ncrede"></div>
                    <div class="fg"><label>Compras</label><input type="number" step="0.01" name="compras" id="f_compras"></div>
                    <div class="fg"><label>Notas Cred. Recibidas</label><input type="number" step="0.01" name="notas_credito_recibidas" id="f_ncredr"></div>
                    <div class="fg"><label>Saldo Anterior IVA</label><input type="number" step="0.01" name="saldo_anterior" id="f_saldoant"></div>
                    <div class="fg"><label>Saldo Libre Disponib.</label><input type="number" step="0.01" name="saldo_libre_disponibilidad" id="f_saldolibre"></div>
                    <div class="fg"><label>Retenciones/Percep. IVA</label><input type="number" step="0.01" name="retenciones_percepciones" id="f_retperc"></div>
                </div>
                <h3 style="font-size:.95rem">Ingresos Brutos (estimado)</h3>
                <div class="fgrid">
                    <div class="fg"><label>Actividad</label><input type="text" name="actividad" id="f_actividad"></div>
                    <div class="fg"><label>Neto Ventas Comprobantes</label><input type="number" step="0.01" name="neto_ventas_comprobantes" id="f_netoventas"></div>
                    <div class="fg"><label>Neto Liquid. Granos/Hacienda</label><input type="number" step="0.01" name="neto_liquidaciones" id="f_netoliq"></div>
                    <div class="fg"><label>Aliquota IIBB (%)</label><input type="number" step="0.01" name="alicuota_iibb" id="f_alicuota" value="3"></div>
                    <div class="fg"><label>Pagos a Cuenta (guias IIBB)</label><input type="number" step="0.01" name="pagos_cuenta_iibb" id="f_pagoscta"></div>
                    <div class="fg"><label>Retenciones IIBB</label><input type="number" step="0.01" name="retenciones_iibb" id="f_retiibb"></div>
                </div>
                <div class="mact">
                    <button type="button" class="btn btn-o" onclick="closeIva()">Cancelar</button>
                    <button type="submit" class="btn btn-p">Guardar</button>
                </div>
            </form>
        </div></div>
        <script>
        function closeIva(){{document.getElementById('miva').classList.remove('on');}}
        document.addEventListener('click',function(e){{
            var b=e.target.closest('.ivaBtn');
            if(!b) return;
            document.getElementById('miva_cid').value=b.dataset.cid;
            document.getElementById('miva_nombre_lbl').textContent=b.dataset.nombre;
            document.getElementById('f_ventas').value=b.dataset.ventas;
            document.getElementById('f_ncrede').value=b.dataset.ncrede;
            document.getElementById('f_compras').value=b.dataset.compras;
            document.getElementById('f_ncredr').value=b.dataset.ncredr;
            document.getElementById('f_saldoant').value=b.dataset.saldoant;
            document.getElementById('f_saldolibre').value=b.dataset.saldolibre;
            document.getElementById('f_retperc').value=b.dataset.retperc;
            document.getElementById('f_netoventas').value=b.dataset.netoventas;
            document.getElementById('f_netoliq').value=b.dataset.netoliq;
            document.getElementById('f_actividad').value=b.dataset.actividad;
            document.getElementById('f_alicuota').value=b.dataset.alicuota;
            document.getElementById('f_pagoscta').value=b.dataset.pagoscta;
            document.getElementById('f_retiibb').value=b.dataset.retiibb;
            document.getElementById('miva').classList.add('on');
        }});
        </script>
        '''
        return page("Control IVA", body, "/iva")

    @app.route("/iva/guardar", methods=["POST"])
    @login_req
    def iva_guardar():
        f = request.form
        cliente_id = f.get("cliente_id")
        mes = f.get("mes"); anio = f.get("anio")
        def num(campo):
            try: return float(f.get(campo, 0) or 0)
            except: return 0
        ventas = num("ventas"); ncred_e = num("notas_credito_emitidas")
        compras = num("compras"); ncred_r = num("notas_credito_recibidas")
        saldo_ant = num("saldo_anterior"); saldo_libre = num("saldo_libre_disponibilidad")
        ret_perc = num("retenciones_percepciones")
        neto_ventas = num("neto_ventas_comprobantes"); neto_liq = num("neto_liquidaciones")
        actividad = f.get("actividad", "").strip()
        alicuota = num("alicuota_iibb") or 3
        pagos_cta = num("pagos_cuenta_iibb"); ret_iibb = num("retenciones_iibb")
        conn = conectar(); c = conn.cursor()
        c.execute("""INSERT INTO iva_control(cliente_id,mes,anio,ventas,notas_credito_emitidas,
            compras,notas_credito_recibidas,saldo_anterior,saldo_libre_disponibilidad,
            retenciones_percepciones,neto_ventas_comprobantes,neto_liquidaciones,actividad,
            alicuota_iibb,pagos_cuenta_iibb,retenciones_iibb,fecha_actualizacion,usuario)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(cliente_id,mes,anio) DO UPDATE SET
            ventas=EXCLUDED.ventas, notas_credito_emitidas=EXCLUDED.notas_credito_emitidas,
            compras=EXCLUDED.compras, notas_credito_recibidas=EXCLUDED.notas_credito_recibidas,
            saldo_anterior=EXCLUDED.saldo_anterior, saldo_libre_disponibilidad=EXCLUDED.saldo_libre_disponibilidad,
            retenciones_percepciones=EXCLUDED.retenciones_percepciones,
            neto_ventas_comprobantes=EXCLUDED.neto_ventas_comprobantes,
            neto_liquidaciones=EXCLUDED.neto_liquidaciones, actividad=EXCLUDED.actividad,
            alicuota_iibb=EXCLUDED.alicuota_iibb, pagos_cuenta_iibb=EXCLUDED.pagos_cuenta_iibb,
            retenciones_iibb=EXCLUDED.retenciones_iibb, fecha_actualizacion=EXCLUDED.fecha_actualizacion,
            usuario=EXCLUDED.usuario""",
            (cliente_id, mes, anio, ventas, ncred_e, compras, ncred_r, saldo_ant, saldo_libre,
             ret_perc, neto_ventas, neto_liq, actividad, alicuota, pagos_cta, ret_iibb,
             now_ar(), session.get("display", session.get("user","?"))))
        conn.commit(); conn.close()
        registrar_auditoria("IVA_CONTROL", f"Actualizo control IVA/IIBB periodo {mes}/{anio}", cliente_id)
        return redirect(f"/iva?mes={mes}&anio={anio}")
