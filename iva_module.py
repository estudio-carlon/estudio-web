def register_iva(app):
    from flask import request, redirect, session
    from app import conectar, fmt, now_ar, now_ar_dt, registrar_auditoria, login_req, page, dec

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
        conn.commit()
        # Migraciones incrementales sobre iva_control
        for ddl in [
            "ALTER TABLE iva_control ADD COLUMN IF NOT EXISTS debito_fiscal REAL DEFAULT 0",
            "ALTER TABLE iva_control ADD COLUMN IF NOT EXISTS credito_fiscal REAL DEFAULT 0",
            "ALTER TABLE iva_control ADD COLUMN IF NOT EXISTS liquidaciones_hacienda REAL DEFAULT 0",
            "ALTER TABLE iva_control ADD COLUMN IF NOT EXISTS liquidaciones_grano REAL DEFAULT 0",
            "ALTER TABLE iva_control ADD COLUMN IF NOT EXISTS notas_credito_iibb REAL DEFAULT 0",
        ]:
            try:
                c.execute(ddl); conn.commit()
            except Exception:
                conn.rollback()
        c.close(); conn.close()

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
        c.execute("""SELECT id,nombre,telefono,condicion_fiscal,responsable_inscripto FROM clientes
            WHERE (activo IS NOT FALSE) AND (condicion_fiscal IN ('Responsable Inscripto','Monotributista') OR responsable_inscripto=TRUE)
            ORDER BY nombre""")
        clientes = c.fetchall()
        c.execute("""SELECT cliente_id,ventas,notas_credito_emitidas,compras,notas_credito_recibidas,
            debito_fiscal,credito_fiscal,saldo_anterior,saldo_libre_disponibilidad,retenciones_percepciones,
            neto_ventas_comprobantes,liquidaciones_hacienda,liquidaciones_grano,notas_credito_iibb,
            actividad,alicuota_iibb,pagos_cuenta_iibb,retenciones_iibb
            FROM iva_control WHERE mes=%s AND anio=%s""",(mes,anio))
        datos = {r[0]: r for r in c.fetchall()}
        conn.close()
        filas = ""
        filas_mono = ""
        for cid, nombre, tel_enc, condicion, ri in clientes:
            es_ri = (condicion == "Responsable Inscripto") or ri
            tel_d = (dec(tel_enc) if tel_enc else "") or ""
            tel_limpio = tel_d.replace("-","").replace(" ","").replace("+","")
            d = datos.get(cid)
            if d:
                (_,ventas,ncred_e,compras,ncred_r,deb_fiscal,cred_fiscal,saldo_ant,saldo_libre,ret_perc,
                 comprobantes,liq_hac,liq_gra,nc_iibb,actividad,alicuota,pagos_cta,ret_iibb) = d
            else:
                ventas=ncred_e=compras=ncred_r=deb_fiscal=cred_fiscal=saldo_ant=saldo_libre=ret_perc=0
                comprobantes=liq_hac=liq_gra=nc_iibb=pagos_cta=ret_iibb=0
                actividad=""; alicuota=3
            # Saldo final de IVA: Credito Fiscal + Saldo Tecnico Anterior + SLD + Retenciones/Percepciones - Debito Fiscal
            # Positivo = saldo a favor del contribuyente. Negativo = IVA a pagar.
            saldo_final = (cred_fiscal or 0) + (saldo_ant or 0) + (saldo_libre or 0) + (ret_perc or 0) - (deb_fiscal or 0)
            # Neto de Ventas (base IIBB) = Comprobantes en linea + Liquidaciones Hacienda + Liquidaciones Grano - Notas de Credito
            neto_ventas_iibb = (comprobantes or 0) + (liq_hac or 0) + (liq_gra or 0) - (nc_iibb or 0)
            iibb_est = neto_ventas_iibb * ((alicuota or 0)/100)
            iibb_neto = iibb_est - (pagos_cta or 0) - (ret_iibb or 0)
            if iibb_neto > 0:
                bad_iibb = f'<span class="badge bd">A pagar {fmt(iibb_neto)}</span>'
            else:
                bad_iibb = f'<span class="badge bp">{fmt(iibb_neto)}</span>'
            btn_cargar = (f'<button class="btn btn-o btn-sm ivaBtn"'
                    f' data-cid="{cid}" data-nombre="{nombre}" data-mono="{0 if es_ri else 1}"'
                    f' data-ventas="{ventas or 0}" data-ncrede="{ncred_e or 0}"'
                    f' data-compras="{compras or 0}" data-ncredr="{ncred_r or 0}"'
                    f' data-debfiscal="{deb_fiscal or 0}" data-credfiscal="{cred_fiscal or 0}"'
                    f' data-saldoant="{saldo_ant or 0}" data-saldolibre="{saldo_libre or 0}"'
                    f' data-retperc="{ret_perc or 0}"'
                    f' data-comprobantes="{comprobantes or 0}" data-liqhac="{liq_hac or 0}" data-liqgra="{liq_gra or 0}"'
                    f' data-nciibb="{nc_iibb or 0}" data-actividad="{actividad or ""}"'
                    f' data-alicuota="{alicuota if alicuota is not None else 3}"'
                    f' data-pagoscta="{pagos_cta or 0}" data-retiibb="{ret_iibb or 0}">Cargar</button>')
            if es_ri:
                wa_btn = ""
                if saldo_final < 0:
                    bad_iva = f'<span class="badge bd">IVA a pagar {fmt(abs(saldo_final))}</span>'
                    if tel_limpio:
                        msg = (f"Hola {nombre}! Te escribimos desde Estudio Contable Carlon. "
                               f"Te informamos que en el periodo {MESES_NOM[mes]} {anio} tenes un IVA a pagar de {fmt(abs(saldo_final))}. "
                               f"Si tenes facturas de compra de ese periodo que todavia no nos enviaste, por favor acercalas a la oficina "
                               f"o mandanoslas por foto o mail. Gracias!")
                        msg_attr = msg.replace(chr(34), "&quot;")
                        wa_btn = (f'<button type="button" class="btn btn-wa btn-sm waIvaBtn" '
                                  f'data-tel="{tel_limpio}" data-msg="{msg_attr}" '
                                  f'title="Avisar por WhatsApp">📱 Avisar</button>')
                elif saldo_final > 0:
                    bad_iva = f'<span class="badge bp">Saldo a favor {fmt(saldo_final)}</span>'
                else:
                    bad_iva = '<span class="badge bpar">Sin saldo</span>'
                filas += f'''<tr>
                    <td class="nm">{nombre}</td>
                    <td>{fmt(deb_fiscal)}</td>
                    <td>{fmt(cred_fiscal)}</td>
                    <td>{bad_iva} {wa_btn}</td>
                    <td>{fmt(neto_ventas_iibb)}</td>
                    <td>{bad_iibb}</td>
                    <td>{btn_cargar}</td>
                    </tr>'''
            else:
                filas_mono += f'''<tr>
                    <td class="nm">{nombre}</td>
                    <td>{fmt(neto_ventas_iibb)}</td>
                    <td>{bad_iibb}</td>
                    <td>{btn_cargar}</td>
                    </tr>'''
        body = f'''
        <p class="page-title">Control de IVA e Ingresos Brutos</p>
        <p class="page-sub">Responsables Inscriptos (IVA + IIBB) y Monotributistas (solo IIBB) - calculo mensual estimado</p>
        <div class="arow">
            <a class="btn btn-o btn-sm" href="/iva?mes={pm}&anio={pa}">&larr; Anterior</a>
            <span class="period">{MESES_NOM[mes]} {anio}</span>
            <a class="btn btn-o btn-sm" href="/iva?mes={nm}&anio={na}">Siguiente &rarr;</a>
        </div>
        <h3 style="font-size:1rem;margin:16px 0 8px">Responsables Inscriptos</h3>
        <div class="dtable"><table>
            <thead><tr><th>Cliente</th><th>Debito Fiscal</th><th>Credito Fiscal</th><th>Resultado IVA</th><th>Neto Ventas (IIBB)</th><th>IIBB estimado</th><th></th></tr></thead>
            <tbody>{filas or "<tr><td colspan=7 style='color:var(--muted);text-align:center;padding:16px'>Sin responsables inscriptos</td></tr>"}</tbody>
        </table></div>
        <h3 style="font-size:1rem;margin:22px 0 8px">Monotributistas (solo Ingresos Brutos)</h3>
        <div class="dtable"><table>
            <thead><tr><th>Cliente</th><th>Neto Ventas (IIBB)</th><th>IIBB estimado</th><th></th></tr></thead>
            <tbody>{filas_mono or "<tr><td colspan=4 style='color:var(--muted);text-align:center;padding:16px'>Sin monotributistas</td></tr>"}</tbody>
        </table></div>
        <div class="mo" id="miva"><div class="modal">
            <h3>Control de IVA / IIBB</h3>
            <p class="msub" id="miva_nombre_lbl"></p>
            <form method="post" action="/iva/guardar">
                <input type="hidden" name="cliente_id" id="miva_cid">
                <input type="hidden" name="mes" value="{mes}">
                <input type="hidden" name="anio" value="{anio}">
                <input type="hidden" name="es_monotributista" id="f_esmono" value="0">
                <div id="fieldsetIva">
                <h3 style="font-size:.95rem">IVA</h3>
                <div class="fgrid">
                    <div class="fg"><label>Ventas (bruto)</label><input type="number" step="0.01" name="ventas" id="f_ventas"></div>
                    <div class="fg"><label>Notas Cred. Emitidas</label><input type="number" step="0.01" name="notas_credito_emitidas" id="f_ncrede"></div>
                    <div class="fg"><label>Compras (bruto)</label><input type="number" step="0.01" name="compras" id="f_compras"></div>
                    <div class="fg"><label>Notas Cred. Recibidas</label><input type="number" step="0.01" name="notas_credito_recibidas" id="f_ncredr"></div>
                    <div class="fg"><label>Debito Fiscal</label><input type="number" step="0.01" name="debito_fiscal" id="f_debfiscal"></div>
                    <div class="fg"><label>Credito Fiscal</label><input type="number" step="0.01" name="credito_fiscal" id="f_credfiscal"></div>
                    <div class="fg"><label>Saldo Tecnico Anterior</label><input type="number" step="0.01" name="saldo_anterior" id="f_saldoant"></div>
                    <div class="fg"><label>Saldo de Libre Disponibilidad (SLD)</label><input type="number" step="0.01" name="saldo_libre_disponibilidad" id="f_saldolibre"></div>
                    <div class="fg"><label>Retenciones y Percepciones del periodo</label><input type="number" step="0.01" name="retenciones_percepciones" id="f_retperc"></div>
                </div>
                <div class="info-box" style="margin-bottom:12px">
                    El saldo final de IVA sale de: Credito Fiscal + Saldo Tecnico Anterior + SLD + Retenciones/Percepciones &minus; Debito Fiscal.
                    Si da positivo es <b>saldo a favor</b> del contribuyente; si da negativo es <b>IVA a pagar</b>.
                </div>
                </div>
                <h3 style="font-size:.95rem">Ingresos Brutos (estimado)</h3>
                <div class="fgrid">
                    <div class="fg"><label>Actividad</label><input type="text" name="actividad" id="f_actividad"></div>
                    <div class="fg"><label>Ventas Comprobantes en Linea</label><input type="number" step="0.01" name="neto_ventas_comprobantes" id="f_comprobantes"></div>
                    <div class="fg"><label>Liquidaciones de Hacienda</label><input type="number" step="0.01" name="liquidaciones_hacienda" id="f_liqhac"></div>
                    <div class="fg"><label>Liquidaciones de Grano</label><input type="number" step="0.01" name="liquidaciones_grano" id="f_liqgra"></div>
                    <div class="fg"><label>Notas de Credito (a restar)</label><input type="number" step="0.01" name="notas_credito_iibb" id="f_nciibb"></div>
                    <div class="fg"><label>Aliquota IIBB (%)</label><input type="number" step="0.01" name="alicuota_iibb" id="f_alicuota" value="3"></div>
                    <div class="fg"><label>Pagos a Cuenta (guias pagadas de Rentas)</label><input type="number" step="0.01" name="pagos_cuenta_iibb" id="f_pagoscta"></div>
                    <div class="fg"><label>Retenciones y Percepciones IIBB del periodo</label><input type="number" step="0.01" name="retenciones_iibb" id="f_retiibb"></div>
                </div>
                <div class="info-box" style="margin-bottom:12px">
                    Neto de Ventas = Comprobantes en linea + Liquidaciones de Hacienda + Liquidaciones de Grano &minus; Notas de Credito.<br>
                    IIBB estimado = Neto de Ventas &times; Aliquota. IIBB a pagar = IIBB estimado &minus; Pagos a Cuenta &minus; Retenciones/Percepciones.
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
            var w=e.target.closest('.waIvaBtn');
            if(w){{
                window.open('https://wa.me/54'+w.dataset.tel.replace(/[^0-9]/g,'')+'?text='+encodeURIComponent(w.dataset.msg),'_blank');
                return;
            }}
            var b=e.target.closest('.ivaBtn');
            if(!b) return;
            document.getElementById('miva_cid').value=b.dataset.cid;
            document.getElementById('miva_nombre_lbl').textContent=b.dataset.nombre;
            document.getElementById('f_ventas').value=b.dataset.ventas;
            document.getElementById('f_ncrede').value=b.dataset.ncrede;
            document.getElementById('f_compras').value=b.dataset.compras;
            document.getElementById('f_ncredr').value=b.dataset.ncredr;
            document.getElementById('f_debfiscal').value=b.dataset.debfiscal;
            document.getElementById('f_credfiscal').value=b.dataset.credfiscal;
            document.getElementById('f_saldoant').value=b.dataset.saldoant;
            document.getElementById('f_saldolibre').value=b.dataset.saldolibre;
            document.getElementById('f_retperc').value=b.dataset.retperc;
            document.getElementById('f_comprobantes').value=b.dataset.comprobantes;
            document.getElementById('f_liqhac').value=b.dataset.liqhac;
            document.getElementById('f_liqgra').value=b.dataset.liqgra;
            document.getElementById('f_nciibb').value=b.dataset.nciibb;
            document.getElementById('f_actividad').value=b.dataset.actividad;
            document.getElementById('f_alicuota').value=b.dataset.alicuota;
            document.getElementById('f_pagoscta').value=b.dataset.pagoscta;
            document.getElementById('f_retiibb').value=b.dataset.retiibb;
            var esMono=b.dataset.mono==='1';
            document.getElementById('f_esmono').value=esMono?'1':'0';
            document.getElementById('fieldsetIva').style.display=esMono?'none':'';
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
        deb_fiscal = num("debito_fiscal"); cred_fiscal = num("credito_fiscal")
        saldo_ant = num("saldo_anterior"); saldo_libre = num("saldo_libre_disponibilidad")
        ret_perc = num("retenciones_percepciones")
        comprobantes = num("neto_ventas_comprobantes")
        liq_hac = num("liquidaciones_hacienda"); liq_gra = num("liquidaciones_grano")
        nc_iibb = num("notas_credito_iibb")
        actividad = f.get("actividad", "").strip()
        alicuota = num("alicuota_iibb") or 3
        pagos_cta = num("pagos_cuenta_iibb"); ret_iibb = num("retenciones_iibb")
        conn = conectar(); c = conn.cursor()
        c.execute("""INSERT INTO iva_control(cliente_id,mes,anio,ventas,notas_credito_emitidas,
            compras,notas_credito_recibidas,debito_fiscal,credito_fiscal,saldo_anterior,saldo_libre_disponibilidad,
            retenciones_percepciones,neto_ventas_comprobantes,liquidaciones_hacienda,liquidaciones_grano,
            notas_credito_iibb,actividad,alicuota_iibb,pagos_cuenta_iibb,retenciones_iibb,fecha_actualizacion,usuario)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(cliente_id,mes,anio) DO UPDATE SET
            ventas=EXCLUDED.ventas, notas_credito_emitidas=EXCLUDED.notas_credito_emitidas,
            compras=EXCLUDED.compras, notas_credito_recibidas=EXCLUDED.notas_credito_recibidas,
            debito_fiscal=EXCLUDED.debito_fiscal, credito_fiscal=EXCLUDED.credito_fiscal,
            saldo_anterior=EXCLUDED.saldo_anterior, saldo_libre_disponibilidad=EXCLUDED.saldo_libre_disponibilidad,
            retenciones_percepciones=EXCLUDED.retenciones_percepciones,
            neto_ventas_comprobantes=EXCLUDED.neto_ventas_comprobantes,
            liquidaciones_hacienda=EXCLUDED.liquidaciones_hacienda,
            liquidaciones_grano=EXCLUDED.liquidaciones_grano,
            notas_credito_iibb=EXCLUDED.notas_credito_iibb,
            actividad=EXCLUDED.actividad,
            alicuota_iibb=EXCLUDED.alicuota_iibb, pagos_cuenta_iibb=EXCLUDED.pagos_cuenta_iibb,
            retenciones_iibb=EXCLUDED.retenciones_iibb, fecha_actualizacion=EXCLUDED.fecha_actualizacion,
            usuario=EXCLUDED.usuario""",
            (cliente_id, mes, anio, ventas, ncred_e, compras, ncred_r, deb_fiscal, cred_fiscal, saldo_ant, saldo_libre,
             ret_perc, comprobantes, liq_hac, liq_gra, nc_iibb, actividad, alicuota, pagos_cta, ret_iibb,
             now_ar(), session.get("display", session.get("user","?"))))
        conn.commit(); conn.close()
        registrar_auditoria("IVA_CONTROL", f"Actualizo control IVA/IIBB periodo {mes}/{anio}", cliente_id)
        return redirect(f"/iva?mes={mes}&anio={anio}")
