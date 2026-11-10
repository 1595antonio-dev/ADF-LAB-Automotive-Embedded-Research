/* ADF LAB / Banco FTDI — edición local y persistencia reproducible.
 * No permite ejecutar escrituras en ECU ni modificar firmware.
 */
'use strict';
(() => {
  const base = window.SEED_DATA;
  if (!base || base.schema !== 3) {
    document.body.insertAdjacentHTML('afterbegin', '<div style="padding:25px;background:#501c1c;color:white">Error: no se cargó el estado base.</div>');
    return;
  }
  let state = structuredClone(base);
  let server = false;
  let busy = false;
  let currentModal = null;
  let currentView = 'panel';
  let saveTimer = null;
  let lastSave = Promise.resolve();
  let toastTimer = null;
  const $ = sel => document.querySelector(sel);
  const $$ = sel => Array.from(document.querySelectorAll(sel));
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'", '&#39;');
  const short = (v,n=76) => String(v ?? '').length>n ? String(v).slice(0,n-1)+'…' : String(v ?? '');
  const today = () => new Date().toISOString().slice(0,10);
  const statuses = ['pendiente','bloqueado','condicional','historico','fallido','medido','verificado'];
  const statusNames = {pendiente:'Pendiente',bloqueado:'Bloqueada',condicional:'Condicional',historico:'Histórico',fallido:'Fallida',medido:'Medida',verificado:'Verificada'};
  const statusClass = (s) => statuses.includes(s) ? s : 'pendiente';
  const pill = (s) => `<span class="tiny-status ${statusClass(s)}">${esc(statusNames[s]||s)}</span>`;
  const evidenceByName = (name) => state.evidencias.find(e=>e.nombre===name);

  function flash(message, isError=false) {
    const node=$('#toast'); node.textContent=message; node.style.background=isError?'#49212b':'#173647'; node.classList.add('on');
    clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove('on'),3900);
  }
  function storageLabel(msg,ok){
    const el=$('#storage-mode');el.className='sync-pill '+(ok?'server':'offline');el.innerHTML=`<span class="small-dot"></span> ${esc(msg)}`;
  }
  function remember() {
    try {localStorage.setItem('adf-me75-ftdi-site-v3',JSON.stringify(state));} catch(e){console.warn('Local Storage',e);}
  }
  async function persist() {
    remember();
    if(!server){storageLabel('Local (exportar copia)',false);return;}
    try {
      const resp = await fetch('/api/estado',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
      const data = await resp.json();
      if(!resp.ok)throw new Error(data.error||'Error de persistencia');
      storageLabel('Guardado en disco · PC',true);
    } catch(e){storageLabel('Sin conexión al servidor',false);flash('No se pudo guardar en el disco: '+e.message,true);server=false;}
  }
  function scheduleSave(){
    remember();
    clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>{ lastSave=lastSave.then(persist);},440);
  }
  function download(name,text,mime='application/json;charset=utf-8'){
    const blob=new Blob([text],{type:mime}), a=document.createElement('a');
    const href=URL.createObjectURL(blob);a.href=href;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),400);
  }
  function exportJSON(){download(`ADF_FTDI_ME75_estado_${today()}.json`,JSON.stringify(state,null,2));}
  function exportCSV(){
    const keys=['id','bloque','titulo','estado','conexiones','senales','comandos','respuesta','tiempo','real','evidencia','criterio','riesgo','nota','prioridad','ultimaRevision','responsable'];
    const rows=[keys,...state.pruebas.map(t=>keys.map(k=>t[k]??''))];
    const csv=rows.map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
    download(`ADF_MATRIZ_FTDI_${today()}.csv`,'\ufeff'+csv,'text/csv;charset=utf-8');
  }
  function addEvent(kind,msg,src=''){
    state.bitacora.unshift({fecha:today(),tipo:kind,texto:msg,fuente:src});
    if(state.bitacora.length>300)state.bitacora.length=300;
  }
  function view(id) {
    if(!$('#view-'+id))return;
    currentView=id;
    $$('.view').forEach(node=>node.classList.toggle('active',node.id==='view-'+id));
    $$('.nav-link').forEach(node=>node.classList.toggle('active',node.dataset.view===id));
    const active=$(`.nav-link[data-view="${id}"]`);
    $('#crumb').textContent=active?.textContent.replace(/\s+/g,' ').trim()||id;
    $('#sidebar').classList.remove('open');
    state.ui.ultimaVista=id;
    remember();
    window.scrollTo({top:0,behavior:'instant'});
  }
  function html(selector,str){const el=$(selector); if(el)el.innerHTML=str;}
  function renderStats(){
    const counts = Object.fromEntries(statuses.map(s=>[s,state.pruebas.filter(t=>t.estado===s).length]));
    const pending = counts.pendiente+counts.bloqueado+counts.condicional+counts.fallido;
    html('#metrics',`<div class="metric"><div class="metric-icon cyan">⌁</div><span>PRUEBAS REGISTRADAS</span><strong>${state.pruebas.length}</strong><small>En matriz editable</small></div>
      <div class="metric"><div class="metric-icon amber">◇</div><span>ACTIVAS / BLOQUEADAS</span><strong>${pending}</strong><small>Requieren contraste</small></div>
      <div class="metric"><div class="metric-icon green">◷</div><span>MUESTRAS REALES</span><strong>790</strong><small>7 nov. · contacto / ralentí / espejos</small></div>
      <div class="metric"><div class="metric-icon red">⊘</div><span>RAM EXCLUSIVA</span><strong class="metric-small">NO</strong><small>0x387F00–0x387F07</small></div>`);
    $('#nav-count').textContent=state.pruebas.length;
    $('#checkpoint-title').textContent=state.checkpoint.titulo;
    $('#checkpoint-id').textContent=state.checkpoint.id;
    $('#checkpoint-detail').textContent=state.checkpoint.detalle;
    $('#checkpoint-next').textContent=state.checkpoint.proximaAccion;
    $('#last-step-title').textContent=state.checkpoint.titulo;
    $('#last-step-text').textContent=state.checkpoint.detalle+' · Siguiente: '+state.checkpoint.proximaAccion;
    const blockCounts={};state.pruebas.forEach(t=>{const v=blockCounts[t.bloque]||{all:0,done:0};v.all++;if(['historico','medido','verificado'].includes(t.estado))v.done++;blockCounts[t.bloque]=v;});
    html('#coverage',Object.entries(blockCounts).map(([n,v])=>`<div class="coverage-line"><div><span>${esc(n)}</span><b>${v.done} / ${v.all} documentados</b></div><div class="bar"><i style="width:${Math.round(v.done/v.all*100)}%"></i></div></div>`).join(''));
  }
  function tableCell(s,n=115){return `<span class="muted-long" title="${esc(s)}">${esc(short(s,n))||'—'}</span>`;}
  function renderTable(){
    const filt=$('#filter-text').value.trim().toLowerCase(),group=$('#filter-block').value,st=$('#filter-status').value;
    const filtered=state.pruebas.filter(t=> (group==='todos'||t.bloque===group) && (st==='todos'||t.estado===st) && (!filt||Object.values(t).some(v=>String(v).toLowerCase().includes(filt))));
    $('#result-count').textContent=`${filtered.length} de ${state.pruebas.length} pruebas`;
    html('#matrix-body', filtered.map(t=>`<tr data-edit-test="${esc(t.id)}"><td><span class="table-id">${esc(t.id)}</span><span class="table-title">${esc(t.titulo)}</span></td><td>${pill(t.estado)}</td><td>${tableCell(t.conexiones)}</td><td>${tableCell(t.senales)}</td><td>${tableCell(t.comandos,150)}</td><td>${tableCell(t.respuesta)}</td><td>${tableCell(t.tiempo)}</td><td>${tableCell(t.real)}</td><td>${tableCell(t.evidencia)}</td><td>${tableCell(t.criterio)}</td><td>${esc(t.riesgo)}</td><td><button class="mini-btn" data-test="${esc(t.id)}">Editar</button></td></tr>`).join('')||'<tr><td colspan="12">No hay pruebas con esos filtros.</td></tr>');
  }
  function setupFilters(){
    const g=$('#filter-block'),s=$('#filter-status');
    const oldGroup=state.ui.filtroBloque||'todos',oldStatus=state.ui.filtroEstado||'todos';
    g.innerHTML='<option value="todos">Todos los bloques</option>'+[...new Set(state.pruebas.map(t=>t.bloque))].sort().map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
    s.innerHTML='<option value="todos">Todos los estados</option>'+statuses.map(x=>`<option value="${x}">${esc(statusNames[x])}</option>`).join('');
    g.value=[...g.options].some(o=>o.value===oldGroup)?oldGroup:'todos';
    s.value=[...s.options].some(o=>o.value===oldStatus)?oldStatus:'todos';
  }
  const routeCards=[
    {cpu:'0x807EE6',title:'Escritor lejano indirecto',detail:'Llamadores CRC 0x805C58 / 0x80C058 y DDLI 0x83B8FE / 0x83BB20. Exclusiones locales documentadas; punteros dinámicos e invocaciones alternativas pendientes.',state:'condicional',test:'RAM-04'},
    {cpu:'0x892BA6',title:'Descriptor y EXTP dinámico',detail:'La rama de escritura requiere tipo descriptor 0. Las 24 llamadas directas están acotadas solo bajo precondiciones; no se demuestra propiedad global.',state:'bloqueado',test:'RAM-05'},
    {cpu:'0x832C30',title:'Test RAM con DPP0 temporal',detail:'Recorrido local hacia 0x38086C–0x380877 con DPP0=0xE0; falta certificación de todos los contextos.',state:'condicional',test:'RAM-06'},
    {cpu:'0x83C0F0',title:'Escritura diagnóstica SID 0x3D',detail:'El guard PASS17 ensayado offline protege intervalos conocidos. No hay validación en ECU ni garantías para otros servicios de escritura.',state:'condicional',test:'RAM-08'},
    {cpu:'0x82586C · 0x825992 · 0x825A84',title:'Tres saltos ISR calculados',detail:'Quedan sus índices y contexto DPP pendientes de demostrar. No sustituir por la estabilidad de los logs FTDI.',state:'bloqueado',test:'ISR-03'},
    {cpu:'0x380F6C / 0x387F00',title:'Integridad DDLI y SRAM',detail:'Un puntero DDLI reorientado puede alcanzar la candidata. SRAM NEC nominal 32 KiB; A13/A14 y alias físico aún sin acreditación completa.',state:'bloqueado',test:'RAM-03'},
  ];
  function renderRoutes(){
    html('#routes-cards',routeCards.map(c=>`<article class="route-card"><div class="route-card-top"><code class="route-address">${esc(c.cpu)}</code>${pill(c.state)}</div><div class="route-desc">${esc(c.title)}</div><p>${esc(c.detail)}</p><button class="mini-btn" data-test="${esc(c.test)}">Editar ${esc(c.test)}</button></article>`).join(''));
    const related=state.pruebas.filter(t=>t.bloque==='ISR / temporización');
    html('#isr-progress',`<div class="route-rows"><div class="route-number"><b>128</b><span>vectores comparados con OEM</span></div><div class="route-number"><b>15</b><span>rutas alcanzables abiertas</span></div><div class="route-number"><b>65</b><span>brechas globales originales</span></div></div><p class="hint">${esc(related.length)} controles ISR en matriz; el cable FTDI aislado no puede emular el C166 ni verificar sus interrupciones.</p>`);
  }
  function renderVersions(){html('#versions-body',state.versiones.map(v=>`<tr><td><span class="table-id">${esc(v.id)}</span><span class="table-title">${esc(v.tipo)} · ${esc(v.nombre)}</span></td><td>${esc(v.version)}</td><td><code>${esc(v.sha256||v.ref)}</code></td><td>${esc(v.fecha)}</td><td>${esc(v.estado)}</td><td>${tableCell(v.nota,230)}</td><td><button class="mini-btn" data-version="${esc(v.id)}">Editar</button></td></tr>`).join(''));}
  function renderSafety(){
    const groups=[...new Set(state.seguridad.map(x=>x.grupo))],good=state.seguridad.filter(x=>x.ok).length;
    $('#safety-count').textContent=`Checklist · ${good}/${state.seguridad.length} verificados`;
    $('#safety-bar').style.width=(state.seguridad.length?100*good/state.seguridad.length:0)+'%';
    html('#safety-list',groups.map(g=>`<div class="safety-group-title">${esc(g)}</div>${state.seguridad.filter(x=>x.grupo===g).map(s=>`<label class="safety-item ${s.ok?'done':''}"><input type="checkbox" data-safety="${esc(s.id)}" ${s.ok?'checked':''}><span>${esc(s.texto)}</span><small class="step-id">${esc(s.id)}</small></label>`).join('')}`).join(''));
  }
  function renderEvidences(){
    html('#evidence-body',state.evidencias.map(e=>`<tr><td><span class="table-id">${esc(e.id)}</span><span class="table-title">${esc(e.nombre)}</span></td><td>${esc(e.tipo)}</td><td><code title="${esc(e.sha256)}">${esc(e.sha256||'—')}</code></td><td>${(e.tamano||0).toLocaleString('es-ES')} B</td><td>${esc(e.fecha)}</td><td>${e.ruta?`<a href="${esc(e.ruta)}" download class="mini-btn">Archivo ↓</a>`:'<span class="tiny-status pendiente">Referencia</span>'} <button class="mini-btn" data-evidence="${esc(e.id)}">Editar</button></td></tr>`).join(''));
    html('#journal',state.bitacora.map(entry=>`<div class="timeline-item"><span class="time">${esc(entry.fecha)} · ${esc(entry.tipo)}</span><p>${esc(entry.texto)}</p><small>${esc(entry.fuente||'Registro manual')}</small></div>`).join(''));
  }
  function renderSteps(){
    html('#steps-list',[...state.pasos].sort((a,b)=>a.prioridad-b.prioridad).map((s,i)=>`<article class="step-card"><div class="step-index">${String(i+1).padStart(2,'0')}</div><div><h3>${esc(s.titulo)} ${pill(s.estado)}</h3><p>${esc(s.detalle)}</p><small>Prerrequisito: ${esc(s.requisito)} · ${esc(s.vinculo)}</small></div><button class="btn btn-outline" data-step="${esc(s.id)}">Editar</button></article>`).join(''));
  }
  function render(){renderStats();setupFilters();renderTable();renderRoutes();renderVersions();renderSafety();renderEvidences();renderSteps();$('#now-year').textContent='2026';}

  // Editor: todas las columnas de una prueba son persistentes y modificables.
  const specs={
    test:{title:'Prueba',fields:[['id','ID'],['titulo','Ensayo'],['bloque','Bloque'],['estado','Estado','status'],['prioridad','Prioridad','priority'],['conexiones','Conexiones / aislamiento','long'],['senales','Señales / señales de control','long'],['comandos','Comandos y tramas','long'],['respuesta','Respuesta esperada','long'],['tiempo','Tiempos y tolerancia','long'],['real','Resultado real medido','long'],['evidencia','Archivo / CSV / captura','long'],['criterio','Criterio de éxito','long'],['riesgo','Nivel de riesgo','risk'],['nota','Notas y límites','long'],['ultimaRevision','Fecha de revisión'],['responsable','Responsable']]},
    version:{title:'Versión',fields:[['id','ID'],['tipo','Clase'],['nombre','Nombre'],['ref','Referencia'],['version','Versión'],['sha256','SHA-256'],['fecha','Fecha'],['estado','Estado'],['nota','Notas','long']]},
    step:{title:'Próximo paso',fields:[['id','ID'],['prioridad','Prioridad'],['titulo','Título'],['detalle','Detalle y criterio','long'],['vinculo','Prueba vinculada'],['requisito','Precondiciones','long'],['estado','Estado','step-status']]},
    checkpoint:{title:'Punto exacto de continuidad',fields:[['id','ID hito'],['fecha','Fecha'],['titulo','Última conclusión verificada','long'],['detalle','Lo demostrado / lo no demostrado','long'],['proximaAccion','Próxima operación precisa','long'],['evidencia','Evidencias / enlaces','long'],['vinculo','Prueba próxima'],['integridad','Restricciones de integridad','long']]},
    journal:{title:'Nueva entrada de bitácora',fields:[['fecha','Fecha'],['tipo','Tipo'],['texto','Descripción factual','long'],['fuente','CSV / documento / enlace']]},
    evidence:{title:'Metadatos de evidencia',fields:[['id','ID'],['nombre','Archivo'],['tipo','Tipo'],['ruta','Ruta relativa'],['sha256','SHA-256'],['tamano','Tamaño (bytes)'],['fecha','Fecha'],['nota','Notas','long']]}
  };
  function options(type,selected){const data= type==='status'?statuses:type==='priority'?['alta','media','baja']:type==='risk'?['bajo','medio','alto']:['pendiente','bloqueado','en_curso','completado'];return `${data.map(v=>`<option value="${esc(v)}" ${selected===v?'selected':''}>${esc(type==='status'?statusNames[v]||v:v)}</option>`).join('')}`;}
  function openEditor(kind,id=null){
    const config=specs[kind];if(!config)return;
    const list={test:state.pruebas,version:state.versiones,step:state.pasos,evidence:state.evidencias};
    const obj=kind==='checkpoint'?state.checkpoint:kind==='journal'?{fecha:today(),tipo:'Observación',texto:'',fuente:''}: id===null?{}:list[kind].find(x=>x.id===id);
    if(!obj){flash('No se encuentra la entrada solicitada',true);return;}
    currentModal={kind,id,oldId:id,fields:config.fields};
    $('#modal-kicker').textContent=kind==='checkpoint'?'PUNTO EXACTO DE CONTINUACIÓN':'EDITOR PERSISTENTE';
    $('#modal-title').textContent=`${id?'Editar':'Crear'} · ${config.title}`;
    const items=config.fields.map(([field,label,t])=>{
      let control;
      if(t==='long') control=`<textarea name="${esc(field)}" rows="3">${esc(obj[field]??'')}</textarea>`;
      else if(['status','priority','risk','step-status'].includes(t)) control=`<select name="${esc(field)}">${options(t,obj[field])}</select>`;
      else control=`<input name="${esc(field)}" value="${esc(obj[field]??'')}" ${field==='id'&&id?'readonly':''}>`;
      return `<div class="modal-field"><label for="field-${esc(field)}">${esc(label)}</label>${control}</div>`;
    }).join('');
    $('#modal-fields').innerHTML=items;
    $('#modal-delete').style.display=(kind==='journal'||kind==='checkpoint'||(kind==='test'&&id?.startsWith('FTDI-')))?'none':(id?'inline-block':'none');
    $('#edit-modal').showModal();
  }
  function closeEditor(){currentModal=null;$('#edit-modal').close();}
  function saveEditor(){
    if(!currentModal)return;
    const {kind,id,fields}=currentModal;
    const fd=new FormData($('#modal-form'));
    const obj={}; for(const [key] of fields)obj[key]=String(fd.get(key)||'').trim();
    if(kind!=='checkpoint'&&kind!=='journal'&&!obj.id){flash('ID requerido',true);return;}
    if(kind==='checkpoint'){
      // Never silently overwrite actual technical state with an unconditional approval.
      if(/reservad[ao]|apto para flashear|flasheable/i.test(obj.titulo) && !obj.evidencia){flash('Requiere evidencia trazable para aprobar reserva',true);return;}
      state.checkpoint=obj;
    } else if(kind==='journal'){if(!obj.texto){flash('Anota el hecho verificado',true);return;} state.bitacora.unshift(obj);}
    else {
      const list={test:state.pruebas,version:state.versiones,step:state.pasos,evidence:state.evidencias}[kind];
      const index=id===null?-1:list.findIndex(x=>x.id===id);
      if(index<0&&list.some(x=>x.id===obj.id)){flash('Ese ID ya existe',true);return;}
      if(kind==='step')obj.prioridad=Math.max(1,Number(obj.prioridad)||999);
      if(kind==='evidence')obj.tamano=Math.max(0,Number(obj.tamano)||0);
      if(index>=0)list[index]=obj;else list.push(obj);
      if(kind==='test')addEvent('Actualización de ensayo',`${obj.id} · ${obj.titulo} · ${obj.estado}`,obj.evidencia||'Matriz');
    }
    closeEditor();scheduleSave();render();flash('Registro guardado');
  }

  async function uploadEvidence(files){
    if(!files?.length)return;
    let count=0;
    for(const file of files){
      if(file.size>12*1024*1024){flash('Archivo demasiado grande: '+file.name,true);continue;}
      if(!server){flash('Necesitas el servidor local para guardar adjuntos. Usa INICIAR_SITE.bat',true);return;}
      try {
        const r=await fetch('/api/subir?nombre='+encodeURIComponent(file.name),{method:'POST',body:file});
        const data=await r.json();if(!r.ok)throw new Error(data.error||'No se pudo adjuntar');
        let id='E-'+String(state.evidencias.length+1).padStart(2,'0');
        while(state.evidencias.some(x=>x.id===id))id='E-'+Math.random().toString(36).slice(2,7).toUpperCase();
        state.evidencias.unshift({id,nombre:data.nombre,tipo:'Subido al Site',ruta:data.ruta,tamano:data.tamano,sha256:data.sha256,fecha:today(),nota:'Adjunto desde panel; resultado no validado automáticamente'});
        addEvent('Evidencia añadida',data.nombre,data.ruta);count++;
      } catch(e){flash(`Error al subir ${file.name}: ${e.message}`,true);}
    }
    if(count){scheduleSave();render();flash(count+' evidencia(s) añadida(s) con SHA-256');}
  }
  async function detectPorts(){
    if(!server){html('#port-results','El Site está en modo estático. Abre INICIAR_SITE.bat en Windows para enumerar USB.');return;}
    html('#port-results','Enumerando puertos sin abrir ninguno…');
    try{const resp=await fetch('/api/puertos');const j=await resp.json();if(!resp.ok)throw Error(j.error||'Error');
      html('#port-results',j.disponible? j.puertos.length?j.puertos.map(p=>`<div><b>${esc(p.dispositivo)}</b> · ${esc(p.descripcion)}<div>Serie: ${esc(p.serial||'N/D')} · VID:PID ${esc(p.vid)}:${esc(p.pid)}</div></div>`).join('<hr>'):'No hay puertos seriales accesibles en este equipo.':esc(j.mensaje));
      if(j.puertos?.length){const match=j.puertos.find(p=>p.serial==='REDACTED_SERIAL');if(match){$('#ftdi-port').value=match.dispositivo;flash('FTDI REDACTED_SERIAL localizado · '+match.dispositivo);}}
    }catch(e){html('#port-results',esc(e.message));}
  }
  async function executeLoopback(){
    if(busy)return;
    if(!server){flash('Arranca el servidor local del PC primero',true);return;}
    const noEcu=$('#assert-no-ecu').checked,ttl=$('#assert-ttl').checked;
    if(!noEcu||!ttl){flash('Confirma ambas condiciones de aislamiento eléctrico',true);return;}
    const p=$('#ftdi-port').value.trim(), baud=Number($('#ftdi-baud').value), attempts=Number($('#ftdi-attempts').value);
    if(!p||attempts<1||attempts>100){flash('Selecciona puerto y repeticiones 1–100',true);return;}
    if(!confirm('Confirmación: la ECU está desconectada y el FTDI tiene un lazo TTL aislado verificado, no K-Line 12 V. ¿Ejecutar solo UART loopback?'))return;
    busy=true;$('#btn-run-ftdi').disabled=true;html('#ftdi-results','Realizando lazo TTL aislado. No interpretar como respuesta de ECU…');
    try {
      const r=await fetch('/api/banco',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modo:'loopback',puerto:p,baud,intentos:attempts,sin_ecu:noEcu,fixture_ttl:ttl})});
      const d=await r.json();if(!r.ok)throw Error(d.error||'Error de UART');
      html('#ftdi-results',esc(JSON.stringify(d,null,2)));
      const ref='evidencias/'+d.archivo;
      const item=state.pruebas.find(x=>x.id==='FTDI-02');
      if(item){item.estado=d.satisfactorio?'medido':'fallido';item.real=`${d.correctos}/${d.ensayos} eco correcto, p50 ${d.latencia_mediana_ms} ms, rango ${d.latencia_min_ms}–${d.latencia_max_ms} ms. SOLO LAZO TTL.`;item.evidencia=d.archivo;item.ultimaRevision=today();}
      state.evidencias.unshift({id:'E-'+Date.now(),nombre:d.archivo,tipo:'Banco FTDI · medido',ruta:ref,tamano:d.tamano,sha256:d.sha256,fecha:today(),nota:'Ensayo real de lazo TTL aislado; no mide ECU / ISR'});
      addEvent('Medición FTDI real',`FTDI-02 · ${d.correctos}/${d.ensayos} tramas iguales; ${d.latencia_mediana_ms} ms mediana`,ref);
      scheduleSave();render();flash('Ensayo terminado. CSV generado en evidencias/');
    }catch(e){html('#ftdi-results','ERROR: '+esc(e.message));flash(e.message,true);}
    finally{busy=false;$('#btn-run-ftdi').disabled=false;}
  }
  function wire(){
    $$('.nav-link').forEach(btn=>btn.addEventListener('click',()=>view(btn.dataset.view)));
    $('#menu-mobile').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
    document.addEventListener('click',e=>{
      const gt=e.target.closest('[data-goto]');if(gt){view(gt.dataset.goto);return;}
      const bt=e.target.closest('[data-test]');if(bt){openEditor('test',bt.dataset.test);return;}
      const ve=e.target.closest('[data-version]');if(ve){openEditor('version',ve.dataset.version);return;}
      const se=e.target.closest('[data-step]');if(se){openEditor('step',se.dataset.step);return;}
      const ev=e.target.closest('[data-evidence]');if(ev){openEditor('evidence',ev.dataset.evidence);return;}
      const tr=e.target.closest('tr[data-edit-test]');if(tr){openEditor('test',tr.dataset.editTest);return;}
    });
    $('#filter-text').addEventListener('input',renderTable);
    $('#filter-block').addEventListener('change',()=>{state.ui.filtroBloque=$('#filter-block').value;remember();renderTable();});
    $('#filter-status').addEventListener('change',()=>{state.ui.filtroEstado=$('#filter-status').value;remember();renderTable();});
    $('#btn-add-test').addEventListener('click',()=>openEditor('test'));
    $('#btn-new-version').addEventListener('click',()=>openEditor('version'));
    $('#btn-add-event').addEventListener('click',()=>openEditor('journal'));
    $('#edit-checkpoint').addEventListener('click',()=>openEditor('checkpoint'));
    $('#btn-edit-next').addEventListener('click',()=>openEditor('checkpoint'));
    $('#go-routes-matrix').addEventListener('click',()=>{view('matriz');$('#filter-block').value='RAM / DPP';renderTable();});
    $('#diag-tests').addEventListener('click',()=>{view('matriz');$('#filter-block').value='Diagnóstico';renderTable();});
    $('#btn-export-global').addEventListener('click',exportJSON);
    $('#btn-export-csv').addEventListener('click',exportCSV);
    $('#btn-backup').addEventListener('click',async()=>{clearTimeout(saveTimer);await persist();exportJSON();flash('Copia JSON creada y estado persistido (si hay servidor)');});
    $('#btn-import-evidence').addEventListener('click',()=>$('#evidence-input').click());
    $('#evidence-input').addEventListener('change',ev=>{uploadEvidence(Array.from(ev.target.files));ev.target.value='';});
    $('#btn-ports').addEventListener('click',detectPorts);
    $('#btn-run-ftdi').addEventListener('click',executeLoopback);
    $('#btn-reset-safety').addEventListener('click',()=>{
      if(!confirm('¿Restablecer el checklist a las marcas iniciales documentadas?'))return;
      state.seguridad=structuredClone(base.seguridad);scheduleSave();render();flash('Checklist restaurado');
    });
    document.addEventListener('change',e=>{
      const safety=e.target.closest('[data-safety]');if(!safety)return;
      const item=state.seguridad.find(s=>s.id===safety.dataset.safety);if(!item)return;
      item.ok=safety.checked;
      addEvent('Checklist de seguridad',item.id+' '+(item.ok?'confirmado':'pendiente'),'Checklist');
      scheduleSave();renderSafety();renderEvidences();
    });
    $('#modal-close').addEventListener('click',closeEditor);
    $('#modal-cancel').addEventListener('click',closeEditor);
    $('#modal-form').addEventListener('submit',e=>{e.preventDefault();saveEditor();});
    $('#modal-delete').addEventListener('click',()=>{
      if(!currentModal||currentModal.id===null)return;
      if(!confirm('¿Eliminar este registro de tu matriz o catálogo?'))return;
      const {kind,id}=currentModal;const lists={test:state.pruebas,version:state.versiones,step:state.pasos,evidence:state.evidencias};
      const list=lists[kind];if(!list)return;
      const index=list.findIndex(x=>x.id===id);if(index>=0)list.splice(index,1);
      closeEditor();scheduleSave();render();flash('Entrada eliminada de la vista, no del archivo de evidencia física');
    });
    // Restore JSON uploads using an additional control within the toolbar.
    const input=document.createElement('input');input.type='file';input.accept='.json';input.hidden=true;document.body.appendChild(input);
    const btn=document.createElement('button');btn.textContent='↥ Importar copia';btn.className='btn btn-quiet';btn.id='btn-import-state';
    $('#btn-export-global').insertAdjacentElement('beforebegin',btn);
    btn.addEventListener('click',()=>input.click());
    input.addEventListener('change',async()=>{
      const file=input.files?.[0];input.value='';if(!file)return;
      try{const restored=JSON.parse(await file.text());
        if(restored.schema!==3||!Array.isArray(restored.pruebas)||!Array.isArray(restored.evidencias)||!Array.isArray(restored.versiones)||!Array.isArray(restored.seguridad))throw Error('Formato de backup incompatible');
        if(!confirm(`Importar ${restored.pruebas.length} pruebas y sustituir el panel actual? Exporta copia antes si hay datos nuevos.`))return;
        state=restored; scheduleSave();render();flash('Copia importada y guardada');
      }catch(e){flash('Error de importación: '+e.message,true);}
    });
  }
  async function init(){
    wire();
    try {
      const response=await fetch('/api/estado',{cache:'no-store'});
      if(!response.ok)throw Error('Sin API');
      const data=await response.json();
      if(data.schema!==3||!Array.isArray(data.pruebas))throw Error('Datos del servidor inválidos');
      state=data;server=true;storageLabel('Guardado en disco · PC',true);
    }catch(e){
      try{const previous=JSON.parse(localStorage.getItem('adf-me75-ftdi-site-v3'));
        if(previous&&previous.schema===3&&Array.isArray(previous.pruebas))state=previous;
      }catch(_){/* static default */}
      server=false;storageLabel('Solo navegador · sin backend',false);
    }
    render();view(state.ui?.ultimaVista||'panel');
  }
  init();
})();
