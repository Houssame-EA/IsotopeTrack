/* Interactive Evaluate-K view. Sweeps K via the Python engine, draws the
   silhouette / Calinski-Harabasz / Davies-Bouldin curves, and lets you click a
   K to apply it. Vanilla JS + Canvas, talks to Python over QWebChannel. */

"use strict";

const THEME = { text:'#d4d4d4', muted:'#888', bg:'#1e1e1e', accent:'#4dd0e1',
  good:'#57d38c', warn:'#f0a955', stroke:'#333' };
const COL = { silhouette:'accent', calinski:'good', davies_bouldin:'warn' };

const E = { backend:null, algos:[], algo:'K-Means', kMin:2, kMax:10,
  results:[], running:false, hoverK:null };

const $ = (id) => document.getElementById(id);
const canvas = $('curve'), ctx = canvas.getContext('2d');
let DPR = window.devicePixelRatio || 1;

/** Connect to the Qt backend, or no-op if not present. */
function boot(){
  if(window.qt && qt.webChannelTransport && typeof QWebChannel!=='undefined'){
    new QWebChannel(qt.webChannelTransport, (ch)=>wire(ch.objects.backend));
  } else { $('note').textContent='Open this inside the app to evaluate.'; }
}
/** Wire the backend: pull config/theme and expose the push receivers. */
function wire(backend){
  E.backend=backend;
  backend.get_theme((t)=>applyTheme(JSON.parse(t)));
  backend.get_config((c)=>onConfig(JSON.parse(c)));
  window.__clusterEval={
    pushK(r){ onK(r); },
    done(s){ E.running=false; finishEval(s); },
  };
}

/** Apply the app palette CSS variables and canvas colours. */
function applyTheme(v){
  if(!v) return; const root=document.documentElement.style;
  const map={bg:'--bg',bg2:'--bg2',panel:'--panel',chip:'--chip',stroke:'--stroke',
    stroke2:'--stroke2',text:'--text',muted:'--muted',muted2:'--muted2',accent:'--accent',
    accent2:'--accent2',good:'--good',warn:'--warn',bad:'--bad'};
  for(const k in map) if(v[k]) root.setProperty(map[k],v[k]);
  THEME.text=v.text||THEME.text; THEME.muted=v.muted2||v.muted||THEME.muted;
  THEME.bg=v.bg||THEME.bg; THEME.accent=v.accent||THEME.accent;
  THEME.good=v.good||THEME.good; THEME.warn=v.warn||THEME.warn;
  THEME.stroke=v.stroke2||THEME.stroke;
  $('swSil').style.background=THEME.accent;
  $('swCal').style.background=THEME.good;
  $('swDb').style.background=THEME.warn;
}
window.applyTheme=applyTheme;
function metricColor(m){ return m==='silhouette'?THEME.accent:m==='calinski'?THEME.good:THEME.warn; }

/** Populate controls from the shared config. */
function onConfig(c){
  if(c.theme) applyTheme(c.theme);
  E.algos=c.algorithms||['K-Means']; E.algo=c.algorithm||'K-Means';
  E.kMin=c.k_min||2; E.kMax=c.k_max||10;
  const sel=$('algoSel'); sel.innerHTML='';
  for(const a of E.algos){ const o=document.createElement('option'); o.value=a; o.textContent=a; sel.appendChild(o); }
  sel.value=E.algo;
  sel.onchange=()=>{ E.algo=sel.value;
    if(E.backend && E.backend.set_algorithm) E.backend.set_algorithm(E.algo); };
  setRange('kMin','vKmin',E.kMin,2,30);
  setRange('kMax','vKmax',E.kMax,3,60);
}
/** Persist the current K range to the shared config (debounced). */
function persistK(){ clearTimeout(persistK._t); persistK._t=setTimeout(()=>{
  if(E.backend && E.backend.set_krange) E.backend.set_krange(+$('kMin').value,+$('kMax').value); },300); }
// Triggered by the toolbar "① Evaluate K": re-sync config from the app, then run.
window.__evalSyncAndRun=(cfgStr)=>{ try{ onConfig(JSON.parse(cfgStr)); }catch(e){} runEval(); };
// Re-sync controls with the shared config when the tab is shown (no run).
window.__evalSync=(cfgStr)=>{ try{ onConfig(JSON.parse(cfgStr)); }catch(e){} };
function setRange(id,lbl,val,mn,mx){ const r=$(id); r.value=val; $(lbl).textContent=val;
  r.style.setProperty('--pct',((val-mn)/(mx-mn)*100)+'%'); }

/** Start a K sweep. */
function runEval(){
  if(!E.backend) return;
  E.kMin=+$('kMin').value; E.kMax=Math.max(E.kMin+1,+$('kMax').value);
  E.results=[]; E.running=true; E.hoverK=null;
  $('empty').classList.remove('show');
  $('note').textContent=`Evaluating ${E.algo}, K=${E.kMin}…${E.kMax}`;
  E.backend.run_evaluation(E.algo, E.kMin, E.kMax);
}
/** Receive one K's scores. */
function onK(r){ E.results.push(r); E.results.sort((a,b)=>a.k-b.k);
  $('note').textContent=`K=${r.k} of ${E.kMax} · ${E.results.length}/${(E.kMax-E.kMin+1)}`; }
/** Finalise after the sweep, computing the best K per metric. */
function finishEval(s){
  const best=bestKs();
  $('bestSil').textContent=best.silhouette!=null?('K='+best.silhouette):'—';
  $('bestCal').textContent=best.calinski!=null?('K='+best.calinski):'—';
  $('bestDb').textContent=best.davies_bouldin!=null?('K='+best.davies_bouldin):'—';
  $('suggestK').textContent=best.suggested!=null?best.suggested:'—';
  $('note').textContent=`Done — evaluated ${E.results.length} values of K.`;
}
/** Best K per metric (max for silhouette/calinski, min for davies). */
function bestKs(){
  const out={silhouette:null,calinski:null,davies_bouldin:null};
  const pick=(key,dir)=>{ let bk=null,bv=null;
    for(const r of E.results){ const v=r[key];
      if(typeof v!=='number'||!isFinite(v)) continue;
      if(bv==null || (dir>0?v>bv:v<bv)){ bv=v; bk=r.k; } } return bk; };
  out.silhouette=pick('silhouette',1);
  out.calinski=pick('calinski',1);
  out.davies_bouldin=pick('davies_bouldin',-1);
  const votes={}; for(const m of ['silhouette','calinski','davies_bouldin']){
    const k=out[m]; if(k!=null) votes[k]=(votes[k]||0)+1; }
  let sk=out.silhouette, sc=-1;
  for(const k in votes) if(votes[k]>sc){ sc=votes[k]; sk=+k; }
  out.suggested=sk; return out;
}

// ==========================================================================
// Drawing
// ==========================================================================
function resize(){ DPR=window.devicePixelRatio||1;
  canvas.width=canvas.clientWidth*DPR; canvas.height=canvas.clientHeight*DPR;
  ctx.setTransform(DPR,0,0,DPR,0,0); }
const PAD={l:52,r:20,t:28,b:40};
function plotX(k){ const w=canvas.clientWidth; const span=(E.kMax-E.kMin)||1;
  return PAD.l+(k-E.kMin)/span*(w-PAD.l-PAD.r); }
function plotY(norm){ const h=canvas.clientHeight;
  return PAD.t+(1-norm)*(h-PAD.t-PAD.b); }
/** Per-metric min/max for normalising to [0,1] with 1 = best. */
function normFns(){
  const fns={};
  for(const m of ['silhouette','calinski','davies_bouldin']){
    const vs=E.results.map(r=>r[m]).filter(v=>typeof v==='number'&&isFinite(v));
    const mn=Math.min(...vs), mx=Math.max(...vs), rng=(mx-mn)||1;
    const better1=(m!=='davies_bouldin');
    fns[m]=(v)=>{ if(typeof v!=='number'||!isFinite(v)) return null;
      const n=(v-mn)/rng; return better1?n:(1-n); };
  }
  return fns;
}
function draw(){
  const w=canvas.clientWidth,h=canvas.clientHeight; ctx.clearRect(0,0,w,h);
  if(!E.results.length){ requestAnimationFrame(draw); return; }
  // axes
  ctx.strokeStyle=THEME.stroke; ctx.globalAlpha=.6; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(PAD.l,PAD.t); ctx.lineTo(PAD.l,h-PAD.b);
  ctx.lineTo(w-PAD.r,h-PAD.b); ctx.stroke(); ctx.globalAlpha=1;
  ctx.fillStyle=THEME.muted; ctx.font='11px -apple-system,system-ui,sans-serif';
  ctx.textAlign='center'; ctx.textBaseline='top';
  const span=E.kMax-E.kMin, stepK=Math.max(1,Math.round(span/12));
  for(let k=E.kMin;k<=E.kMax;k+=stepK){ ctx.fillText('K='+k, plotX(k), h-PAD.b+6); }
  ctx.save(); ctx.translate(14,(PAD.t+h-PAD.b)/2); ctx.rotate(-Math.PI/2);
  ctx.textBaseline='middle'; ctx.fillText('score (1 = best)',0,0); ctx.restore();

  const fns=normFns(), best=bestKs();
  for(const m of ['silhouette','calinski','davies_bouldin']){
    ctx.strokeStyle=metricColor(m); ctx.lineWidth=2; ctx.globalAlpha=.95; ctx.beginPath();
    let started=false;
    for(const r of E.results){ const n=fns[m](r[m]); if(n==null) continue;
      const x=plotX(r.k),y=plotY(n); if(started) ctx.lineTo(x,y); else {ctx.moveTo(x,y); started=true;} }
    ctx.stroke();
    for(const r of E.results){ const n=fns[m](r[m]); if(n==null) continue;
      ctx.beginPath(); ctx.arc(plotX(r.k),plotY(n),2.5,0,6.283); ctx.fillStyle=metricColor(m); ctx.fill(); }
    const bk=best[m]; if(bk!=null){ const rr=E.results.find(x=>x.k===bk);
      if(rr){ const n=fns[m](rr[m]); ctx.beginPath(); ctx.arc(plotX(bk),plotY(n),5.5,0,6.283);
        ctx.fillStyle=metricColor(m); ctx.fill(); ctx.lineWidth=2; ctx.strokeStyle=THEME.bg; ctx.stroke(); } }
  }
  ctx.globalAlpha=1;
  // suggested-K vertical line
  if(best.suggested!=null){ const x=plotX(best.suggested);
    ctx.strokeStyle=THEME.accent; ctx.globalAlpha=.35; ctx.setLineDash([4,4]); ctx.lineWidth=1.5;
    ctx.beginPath(); ctx.moveTo(x,PAD.t); ctx.lineTo(x,h-PAD.b); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha=1; }
  // hover marker
  if(E.hoverK!=null){ const x=plotX(E.hoverK);
    ctx.strokeStyle=THEME.text; ctx.globalAlpha=.4; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(x,PAD.t); ctx.lineTo(x,h-PAD.b); ctx.stroke(); ctx.globalAlpha=1; }
  requestAnimationFrame(draw);
}

// ==========================================================================
// Interaction
// ==========================================================================
function kAtX(mx){ const w=canvas.clientWidth; const span=(E.kMax-E.kMin)||1;
  const k=Math.round(E.kMin+(mx-PAD.l)/(w-PAD.l-PAD.r)*span);
  return Math.max(E.kMin,Math.min(E.kMax,k)); }
function onHover(e){
  if(!E.results.length){ return; }
  const rect=canvas.getBoundingClientRect(), mx=e.clientX-rect.left;
  const k=kAtX(mx); E.hoverK=k; const r=E.results.find(x=>x.k===k);
  const tip=$('tip'); if(!r){ tip.style.display='none'; return; }
  const fmt=(v)=>(typeof v==='number'&&isFinite(v))?v.toFixed(v<10?3:0):'—';
  tip.innerHTML=`<div class="th">K = ${r.k} · ${r.n_clusters} clusters</div>`+
    `<div class="row"><span style="color:${THEME.accent}">Silhouette</span><b>${fmt(r.silhouette)}</b></div>`+
    `<div class="row"><span style="color:${THEME.good}">Calinski-H.</span><b>${fmt(r.calinski)}</b></div>`+
    `<div class="row"><span style="color:${THEME.warn}">Davies-B.</span><b>${fmt(r.davies_bouldin)}</b></div>`+
    `<div class="row" style="margin-top:4px;color:var(--muted)">click to apply</div>`;
  tip.style.display='block';
  tip.style.left=Math.min(window.innerWidth-200,e.clientX+14)+'px';
  tip.style.top=(e.clientY+14)+'px';
}
function onClick(e){
  if(!E.results.length||!E.backend) return;
  const rect=canvas.getBoundingClientRect(); const k=kAtX(e.clientX-rect.left);
  E.backend.apply_k(k);
  showStatus(`K = ${k} applied — run ② Cluster to see it`);
}
function showStatus(t){ const el=$('status'); el.textContent=t; el.classList.add('show');
  clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),1800); }

function bind(){
  $('menuBtn').onclick=()=>$('panel').classList.toggle('open');
  const pc=$('panelClose'); if(pc) pc.onclick=()=>$('panel').classList.remove('open');
  $('evalBtn').onclick=runEval;
  $('kMin').oninput=()=>{ setRange('kMin','vKmin',+$('kMin').value,2,30); persistK(); };
  $('kMax').oninput=()=>{ setRange('kMax','vKmax',+$('kMax').value,3,60); persistK(); };
  canvas.addEventListener('mousemove',onHover);
  canvas.addEventListener('mouseleave',()=>{ E.hoverK=null; $('tip').style.display='none'; });
  canvas.addEventListener('click',onClick);
  window.addEventListener('resize',resize);
}

window.addEventListener('load',()=>{ resize(); bind(); requestAnimationFrame(draw); boot(); });
