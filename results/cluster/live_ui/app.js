/* Cluster Lab (embedded) — talks to the Python engine over QWebChannel,
   buffers streamed frames, animates the computation on a canvas, and follows
   the app's dark/light palette. Vanilla JS + Canvas 2D, no external libs. */

"use strict";

let PALETTE = ['#2563EB','#DC2626','#16A34A','#D97706','#7C3AED','#0891B2',
  '#DB2777','#65A30D','#EA580C','#4F46E5','#0D9488','#C026D3'];
/** Colour of cluster `c`, honouring any per-cluster override from the legend. */
function colorFor(c){
  if(c < 0) return THEME.noise;
  const o = S.ui.colors[c];
  return o || PALETTE[c % PALETTE.length];
}
 /**
 * User-facing name of a cluster.
 *
 * Labels are 0-based internally but displayed from 1, matching
 * ``_cluster_label_short`` in the main dialog so C1 means the same thing in
 * both places.
 *
 * @param {number} c Internal cluster id, negative for noise.
 * @returns {string} 'C1', 'C2', … or 'Noise'.
 */
function clusterTag(c){ return c < 0 ? 'Noise' : 'C' + (c + 1); }

const THEME = { noise:'#888', text:'#d4d4d4', bg:'#1e1e1e', accent:'#007acc' };

const S = {
  backend:null, schema:null, data:null, palette:PALETTE,
  algo:'K-Means', params:{},
  frames:[], t:0, playing:false, fps:7, loop:false, lastTick:0,
  running:false, hidden:new Set(), focus:null, tween:null, hoverIdx:-1, inertiaHist:[],
  split:false, cmp:null, cmpPending:false, animEnd:null, settlePending:false,
  view:{scale:1, ox:0, oy:0}, dragScrub:false,
  proj:'PCA', projInfo:{}, paramEls:{}, dims:2, rot:{az:0.7, el:0.35}, drag3d:null,
  v3:{scale:1, cx:0, cy:0, center:[0,0,0]},
  insetOn:true, insetCollapsed:false, insetDrag:null, insetResize:null,
  eqOn:true, eqCollapsed:false, legendOn:true,
  ui:{font:'system', fontStyle:'normal', fontSize:13.5,
      labelMode:'Mass + Symbol', pointSize:0, centSize:6.5, colors:{},
      maxIso:4, minPct:1.0},
  exp:{scale:3, fontBoost:1.25, transparent:false},
};

const UI_FONTS = {system:'-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif'};
/** Resolve the Appearance font choice to a CSS font-family stack. */
function uiFontStack(){ return UI_FONTS[S.ui.font] || S.ui.font; }
/** Effective base font size, enlarged while exporting so text stays readable. */
function uiSize(){
  return S.ui.fontSize * (EXPORT ? S.exp.fontBoost : 1);
}
/** Canvas font shorthand at `scale` times the effective font size. */
function uiFont(scale, weight){
  const px = Math.max(7, uiSize() * (scale||1));
  const style = weight || S.ui.fontStyle;
  return (style && style!=='normal' ? style+' ' : '')
    + px.toFixed(1) + 'px ' + uiFontStack();
}

const $ = (id) => document.getElementById(id);
const canvas = $('plot');
const icanvas = $('insetPlot');
let ctx = canvas.getContext('2d');
let ictx = icanvas ? icanvas.getContext('2d') : null;
let EXPORT = null;
let DPR = window.devicePixelRatio || 1;

/** Connect to the Qt backend over QWebChannel, or fall back to a browser-preview mock. */
function boot(){
  const note = $('note');
  try{
    if (window.qt && qt.webChannelTransport && typeof QWebChannel !== 'undefined'){
      new QWebChannel(qt.webChannelTransport, (ch) => {
        if (ch && ch.objects && ch.objects.backend) wire(ch.objects.backend);
        else { note.textContent = 'Connected, but backend object missing'; wire(makeMockBackend()); }
      });
    } else {
      note.textContent = (typeof QWebChannel === 'undefined')
        ? 'QWebChannel script not loaded — showing preview' : 'No Qt transport — showing preview';
      wire(makeMockBackend());
    }
  } catch(e){
    note.textContent = 'Bridge error: ' + e.message + ' — showing preview';
    wire(makeMockBackend());
  }
}
/** Attach backend handlers and load schema, theme and initial state. */
function wire(backend){
  S.backend = backend;
  try{
    backend.stateReady.connect((s)=>{ receiveState(JSON.parse(s)); });
    backend.frameReady.connect((f)=>receiveFrame(JSON.parse(f)));
    backend.runFinished.connect(()=>{ S.running=false; });
    backend.status.connect(showStatus);
  }catch(e){ }
  backend.get_theme((t)=>applyTheme(JSON.parse(t)));
  backend.get_schema((s)=>{ S.schema=JSON.parse(s); buildPanel();
    backend.get_state((st)=>{ receiveState(JSON.parse(st)); }); });
}

let _seenIter = -1, _seenRun = 0;
/** Buffer one computation frame, ignoring duplicates from the signal path. */
function receiveFrame(fr){
  const key = _seenRun + ':' + fr.iter + ':' + (fr.note||'');
  if (key === receiveFrame._last) return;
  receiveFrame._last = key;
  onFrame(fr);
}
/** Apply a new dataset state and re-run. Exact re-deliveries (same seq from the
 *  runJavaScript and signal paths) are ignored so the animation isn't reset. */
function receiveState(st){
  if (st.seq != null && st.seq === receiveState._seq) return;
  receiveState._seq = (st.seq != null) ? st.seq : (receiveState._seq || 0) + 1;
  onState(st);
  if (!st.empty) scheduleRun(!!st.animate);
}
window.__clusterLive = {
  pushFrames(arr){ for(const fr of arr) receiveFrame(fr); },
  setState(st){ receiveState(st); },
  runDone(_s){ S.running=false; },
  projecting(proj,dims){ $('note').textContent=`Computing ${proj} ${dims}D projection…`; },
  compareReady(res){ receiveCompare(res); },
};
 /**
 * Store the scikit-learn comparison result pushed by the bridge.
 * @param {Object} res ``{error, note, labels, centroids, metrics}``.
 */
function receiveCompare(res){
  if(res && res.seq!=null && receiveState._seq!=null && res.seq!==receiveState._seq){
    return;
  }
  S.cmpPending=false;
  if(!res || res.error || !res.labels){
    S.cmp=null;
    showStatus(res && res.error ? 'scikit-learn: '+res.error
                                : 'scikit-learn result unavailable');
  } else {
    S.cmp=res;
    if(res.settle) settleOnCompare();
  }
  fitView();
}
 /**
 * Append the scikit-learn result as the animation's final frame.
 *
 * The stepper illustrates the method; the answer left on screen is the real
 * one. ``S.animEnd`` remembers where the animation itself ended so the split
 * view can still show what the stepper concluded.
 */
function settleOnCompare(){
  const cmp=S.cmp;
  if(!cmp || !cmp.labels || !S.data || cmp.labels.length!==S.data.n) return;
  if(S.playing && S.t < S.frames.length-1){ S.settlePending=true; return; }
  S.settlePending=false;
  if(S.frames.length && S.frames[S.frames.length-1].settled) S.frames.pop();
  S.animEnd=Math.max(0,S.frames.length-1);
  const prev=S.frames.length?frameAt(S.animEnd):null;
  const m=cmp.metrics||{};
  S.frames.push({
    iter:(prev?prev.iter:0)+1,
    note:cmp.note||'Result',
    labels:cmp.labels,
    centroids:cmp.centroids||null,
    positions:null,
    extra:carryExtra(prev),
    converged:true, settled:true,
    metrics:{n_clusters:m.n_clusters, n_noise:m.n_noise},
  });
  S.t=S.frames.length-1;
  S.playing=false; syncPlayBtn();
  const sc=$('scrub'); if(sc){ sc.max=String(S.frames.length-1); sc.value=String(S.t); }
}
 /**
 * Copy a frame's detail view and worked example for the settled frame.
 *
 * Both describe the last step the algorithm took, so their subtitles are
 * marked as belonging to the animation rather than to the settled numbers.
 *
 * @param {?Object} prev The animation's final frame.
 * @returns {Object} An ``extra`` payload, empty when there is nothing to carry.
 */
function carryExtra(prev){
  const src=prev && prev.extra;
  if(!src) return {};
  const out={};
  if(src.inset){
    out.inset=Object.assign({}, src.inset);
    out.inset.subtitle=(out.inset.subtitle?out.inset.subtitle+' · ':'')
      +'from the final animation step';
  }
  if(src.equation){
    out.equation=Object.assign({}, src.equation);
    out.equation.note=(out.equation.note?out.equation.note+' ':'')
      +'(the last step of the animation)';
  }
  return out;
}
/**
 * Ask the bridge to compute the authoritative scikit-learn labels.
 *
 * No-op when the page is running outside the app, where no bridge exists.
 */
function requestCompare(){
  if(!S.backend || typeof S.backend.run_sklearn!=='function') return;
  S.cmpPending=true;
  try{ S.backend.run_sklearn(); }
  catch(e){ S.cmpPending=false; }
}

/** Apply the app palette CSS variables and canvas colours to the page. */
function applyTheme(v){
  if(!v) return;
  const root=document.documentElement.style;
  const map={bg:'--bg',bg2:'--bg2',panel:'--panel',chip:'--chip',stroke:'--stroke',
    stroke2:'--stroke2',text:'--text',muted:'--muted',muted2:'--muted2',accent:'--accent',
    accent2:'--accent2',good:'--good',warn:'--warn',bad:'--bad'};
  for(const k in map) if(v[k]) root.setProperty(map[k], v[k]);
  if(!S.noiseLocked) THEME.noise = v.muted2 || v.muted || '#888';
  THEME.text  = v.text || '#d4d4d4';
  THEME.bg    = v.bg || '#1e1e1e';
  THEME.accent= v.accent || '#007acc';
}
window.applyTheme = applyTheme;

/** Store the dataset state, fit the view and update the header line. */
function onState(state){
  S.data = state;
  S.dims = state.dims || 2;
  if(state.projection) S.proj = state.projection;
  if(state.palette && state.palette.length){ PALETTE=state.palette; S.palette=state.palette; }
  if(state.noise_color){ THEME.noise=state.noise_color; S.noiseLocked=true; }
  if(state.cluster_colors){
    S.ui.colors={};
    for(const k in state.cluster_colors){
      const v=state.cluster_colors[k];
      if(v) S.ui.colors[parseInt(k,10)]=v;
    }
  }
  if(state.theme) applyTheme(state.theme);
  S.paramValues = state.param_values || S.paramValues || {};
  if(state.algorithm) S.algo = state.algorithm;
  reflectConfig(state);
  if(S.schema){ const as=$('algoSel'); if(as) as.value=S.algo; buildAlgoParams(); }
  S.hidden.clear();
  S.focus=null; S.tween=null;
  S.cmp=null; S.animEnd=null; S.settlePending=false;
  // Drop frames from the previous dataset so draw never mixes old labels with
  // the new point set (a new run repopulates them).
  S.frames=[]; S.t=0;
  $('empty').classList.toggle('show', !!state.empty);
  if(state.empty){ return; }
  fitView();
  const v=state.var_ratio||[0,0];
  const proj=state.projection||'PCA';
  const nlbl = (state.n_total && state.n_total>state.n)
    ? `${state.n} of ${state.n_total} particles` : `${state.n} particles`;
  let vtxt='';
  if(proj==='PCA'){
    const pct=v.map(x=>(x*100).toFixed(0)+'%').join(' / ');
    vtxt=`var ${pct} · `;
  }
  $('varInfo').textContent =
    `${proj} · ${S.dims}D · ${vtxt}${nlbl} · ${state.elements.length} elements`;
}

/** Return the current display dimensionality (2 or 3). */
function curDims(){ return (S.data && S.data.dims) || 2; }

 /**
 * Width of the plot area in CSS pixels.
 * @returns {number} The canvas width.
 */
function paneW(){ return canvas.clientWidth; }

 /**
 * 2-D view parameters that frame a bounding box in the canvas.
 * @param {number} x0 Left edge in data units.
 * @param {number} y0 Bottom edge in data units.
 * @param {number} x1 Right edge in data units.
 * @param {number} y1 Top edge in data units.
 * @param {number} [pad=64] Screen-pixel margin kept around the box.
 * @returns {{scale:number, ox:number, oy:number}} Scale and origin offsets.
 */
function viewFor(x0, y0, x1, y1, pad){
  const w=paneW(), h=canvas.clientHeight;
  pad = pad==null ? 64 : pad;
  const sc=Math.min((w-2*pad)/((x1-x0)||1),(h-2*pad)/((y1-y0)||1));
  return {scale:sc,
    ox:pad+(w-2*pad-sc*(x1-x0))/2-sc*x0,
    oy:h-pad-(h-2*pad-sc*(y1-y0))/2+sc*y0};
}
 /**
 * Bounding box of the whole 2-D point cloud.
 * @returns {?number[]} [x0, y0, x1, y1], or null when there is no data.
 */
function dataBounds2(){
  const P=S.data && S.data.xy;
  if(!P || !P.length) return null;
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  for(const p of P){ const x=p[0],y=p[1]; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
  return [x0,y0,x1,y1];
}
/** Fit the 2-D or 3-D view to the current point cloud. */
function fitView(){
  if(!S.data) return;
  S.tween=null;
  if(curDims()===3){ fitView3(); return; }
  const b=dataBounds2(); if(!b) return;
  const v=viewFor(b[0],b[1],b[2],b[3]);
  S.view.scale=v.scale; S.view.ox=v.ox; S.view.oy=v.oy;
}
/** Compute the centre and scale for the 3-D orthographic view. */
function fitView3(){
  const P=S.data.xy; const c=[0,0,0];
  for(const p of P){ c[0]+=p[0]; c[1]+=p[1]; c[2]+=(p[2]||0); }
  c[0]/=P.length; c[1]/=P.length; c[2]/=P.length;
  let mx=1e-6;
  for(const p of P){ const d=Math.hypot(p[0]-c[0],p[1]-c[1],(p[2]||0)-c[2]); if(d>mx)mx=d; }
  const w=paneW(),h=canvas.clientHeight;
  S.v3.cx=w/2; S.v3.cy=h/2; S.v3.center=c;
  S.v3.baseScale=(Math.min(w,h)*0.40)/mx;
  if(!S.v3.zoom) S.v3.zoom=1;
  S.v3.scale=S.v3.baseScale*S.v3.zoom;
}
const wx=(x)=>S.view.ox+x*S.view.scale;
const wy=(y)=>S.view.oy-y*S.view.scale;
const ux=(px)=>(px-S.view.ox)/S.view.scale;
const uy=(py)=>(S.view.oy-py)/S.view.scale;

 /**
 * Round tick values spanning [lo, hi] at a 1/2/5 × 10ⁿ step.
 *
 * @param {number} lo Lower bound in data units.
 * @param {number} hi Upper bound in data units.
 * @param {number} target Roughly how many ticks are wanted.
 * @returns {{values:number[], step:number}} Ticks and the step between them.
 */
function niceTicks(lo, hi, target){
  if(!(hi>lo) || !isFinite(lo) || !isFinite(hi)) return {values:[], step:1};
  const raw=(hi-lo)/Math.max(1,target);
  const mag=Math.pow(10, Math.floor(Math.log10(raw)));
  const n=raw/mag;
  const step=(n<1.5?1:n<3?2:n<7?5:10)*mag;
  const values=[];
  for(let v=Math.ceil(lo/step)*step; v<=hi+step*1e-6; v+=step){
    values.push(Math.abs(v)<step*1e-6 ? 0 : v);
    if(values.length>200) break;
  }
  return {values, step};
}
 /**
 * Format a tick value at a precision suited to the step between ticks.
 *
 * @param {number} v The value.
 * @param {number} step Spacing between ticks.
 * @returns {string} Display text.
 */
function fmtTick(v, step){
  if(v===0) return '0';
  const a=Math.abs(step);
  if(a>=1e4 || a<1e-3) return v.toExponential(1).replace('e+','e');
  return v.toFixed(Math.max(0, Math.ceil(-Math.log10(a))));
}

const DIM_ALPHA = 0.13;
const FOCUS_MAX_ZOOM = 9;
const TWEEN_MS = 420;

 /**
 * Whether cluster `c` should be drawn faded because another cluster has focus.
 * @param {number} c Cluster id.
 * @returns {boolean} True when a different cluster is focused.
 */
function isDimmed(c){ return S.focus!=null && c!==S.focus; }
 /**
 * Positions and labels of the frame currently on screen.
 * @returns {?{pos:number[][], labels:number[]}} Null when no frame matches the
 *   current dataset (e.g. mid re-projection).
 */
function currentCloud(){
  const fr=S.frames.length?frameAt(Math.floor(S.t)):null;
  const labels=fr && fr.labels ? fr.labels : null;
  const pos=(fr && fr.positions) ? fr.positions : (S.data && S.data.xy);
  if(!labels || !pos || labels.length!==pos.length) return null;
  return {pos, labels};
}
 /**
 * Ease-in-out cubic.
 * @param {number} k Progress in [0,1].
 * @returns {number} Eased progress in [0,1].
 */
function ease(k){ return k<0.5 ? 4*k*k*k : 1-Math.pow(-2*k+2,3)/2; }
 /**
 * Start an animated view transition.
 * @param {string} kind '2d' (scale/ox/oy) or '3d' (zoom/center).
 * @param {Object} from View parameters to animate away from.
 * @param {Object} to View parameters to animate towards.
 */
function startTween(kind, from, to){
  S.tween={kind, from, to, t0:(performance.now?performance.now():Date.now()), dur:TWEEN_MS};
}
 /**
 * Advance the running view tween, clearing it once complete.
 * @param {number} now Current timestamp in milliseconds.
 */
function stepTween(now){
  const T=S.tween; if(!T) return;
  const k=Math.min(1,(now-T.t0)/T.dur), e=ease(k);
  const mix=(a,b)=>a+(b-a)*e;
  if(T.kind==='2d'){
    S.view.scale=mix(T.from.scale,T.to.scale);
    S.view.ox=mix(T.from.ox,T.to.ox);
    S.view.oy=mix(T.from.oy,T.to.oy);
  } else {
    S.v3.zoom=mix(T.from.zoom,T.to.zoom);
    S.v3.center=[mix(T.from.center[0],T.to.center[0]),
                 mix(T.from.center[1],T.to.center[1]),
                 mix(T.from.center[2],T.to.center[2])];
    S.v3.scale=(S.v3.baseScale||1)*S.v3.zoom;
  }
  if(k>=1) S.tween=null;
}
 /**
 * Zoom the view onto cluster `c`; pass null to return to the full cloud.
 * Other clusters stay on screen (dimmed), so the context is never lost.
 * @param {?number} c Cluster id, or null to reset.
 * @param {boolean} [instant] Skip the animation (used on resize).
 */
function zoomToCluster(c, instant){
  if(!S.data || S.data.empty) return;
  const cloud=currentCloud();
  const three=curDims()===3;

  if(c==null || !cloud){
    if(three){
      const from={zoom:S.v3.zoom||1, center:(S.v3.center||[0,0,0]).slice()};
      fitView3(); const to={zoom:1, center:(S.v3.center||[0,0,0]).slice()};
      S.v3.zoom=from.zoom; S.v3.center=from.center;
      S.v3.scale=(S.v3.baseScale||1)*S.v3.zoom;
      if(instant){ S.v3.zoom=to.zoom; S.v3.center=to.center;
        S.v3.scale=(S.v3.baseScale||1); S.tween=null; }
      else startTween('3d', from, to);
    } else {
      const b=dataBounds2(); if(!b) return;
      const to=viewFor(b[0],b[1],b[2],b[3]);
      if(instant){ S.view.scale=to.scale; S.view.ox=to.ox; S.view.oy=to.oy; S.tween=null; }
      else startTween('2d', {scale:S.view.scale, ox:S.view.ox, oy:S.view.oy}, to);
    }
    return;
  }

  const {pos, labels}=cloud;
  if(three){
    const cen=[0,0,0]; let n=0;
    for(let i=0;i<pos.length;i++){ if(labels[i]!==c) continue;
      cen[0]+=pos[i][0]; cen[1]+=pos[i][1]; cen[2]+=(pos[i][2]||0); n++; }
    if(!n) return;
    cen[0]/=n; cen[1]/=n; cen[2]/=n;
    let r=1e-6;
    for(let i=0;i<pos.length;i++){ if(labels[i]!==c) continue;
      const d=Math.hypot(pos[i][0]-cen[0],pos[i][1]-cen[1],(pos[i][2]||0)-cen[2]);
      if(d>r) r=d; }
    const full=(Math.min(paneW(),canvas.clientHeight)*0.40)/(S.v3.baseScale||1);
    const zoom=Math.max(1, Math.min(FOCUS_MAX_ZOOM, full/(r*1.6)));
    const from={zoom:S.v3.zoom||1, center:(S.v3.center||[0,0,0]).slice()};
    if(instant){ S.v3.zoom=zoom; S.v3.center=cen;
      S.v3.scale=(S.v3.baseScale||1)*zoom; S.tween=null; }
    else startTween('3d', from, {zoom, center:cen});
    return;
  }

  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9,n=0;
  for(let i=0;i<pos.length;i++){ if(labels[i]!==c) continue;
    const p=pos[i];
    if(p[0]<x0)x0=p[0]; if(p[0]>x1)x1=p[0];
    if(p[1]<y0)y0=p[1]; if(p[1]>y1)y1=p[1]; n++; }
  if(!n) return;
  const b=dataBounds2()||[x0,y0,x1,y1];
  const minSpan=Math.max((b[2]-b[0]),(b[3]-b[1]))*0.02 || 1e-6;
  if(x1-x0<minSpan){ const m=(x0+x1)/2; x0=m-minSpan/2; x1=m+minSpan/2; }
  if(y1-y0<minSpan){ const m=(y0+y1)/2; y0=m-minSpan/2; y1=m+minSpan/2; }
  const mx=(x1-x0)*0.18, my=(y1-y0)*0.18;
  let to=viewFor(x0-mx, y0-my, x1+mx, y1+my);
  const base=viewFor(b[0],b[1],b[2],b[3]);
  if(to.scale > base.scale*FOCUS_MAX_ZOOM){
    const cx=(x0+x1)/2, cy=(y0+y1)/2, sc=base.scale*FOCUS_MAX_ZOOM;
    to={scale:sc, ox:paneW()/2-sc*cx, oy:canvas.clientHeight/2+sc*cy};
  }
  if(instant){ S.view.scale=to.scale; S.view.ox=to.ox; S.view.oy=to.oy; S.tween=null; }
  else startTween('2d', {scale:S.view.scale, ox:S.view.ox, oy:S.view.oy}, to);
}
 /**
 * Focus a cluster: zoom to it, dim the others and refresh the legend.
 * Focusing the already-focused cluster clears the focus instead.
 * @param {?number} c Cluster id, or null to clear the focus.
 */
function setFocus(c){
  S.focus = (c==null || S.focus===c) ? null : c;
  zoomToCluster(S.focus);
  refreshLegend();
}

/** Project a data point to screen coordinates (2-D pan/zoom or 3-D rotate). */
function screen(p){
  if(curDims()===3){
    const {az,el}=S.rot, ca=Math.cos(az),sa=Math.sin(az),ce=Math.cos(el),se=Math.sin(el);
    const c=S.v3.center||[0,0,0];
    const x=p[0]-c[0], y=p[1]-c[1], z=(p[2]||0)-c[2];
    const x1=ca*x - sa*z, z1=sa*x + ca*z;
    const y1=ce*y - se*z1, z2=se*y + ce*z1;
    return [S.v3.cx + x1*S.v3.scale, S.v3.cy - y1*S.v3.scale, z2];
  }
  return [wx(p[0]), wy(p[1]), 0];
}

let runTimer=null;
/** Debounce and trigger a clustering run. `animate` plays it; otherwise the
 *  final result is shown without playing (used when just opening the tab). */
function scheduleRun(animate){ clearTimeout(runTimer);
  const a=(animate!==false); runTimer=setTimeout(()=>run(a),160); }
/** Start a clustering run for the current algorithm and parameters. */
function run(animate){
  if(!S.backend||!S.data||S.data.empty) return;
  S.backend.stop();
  S._animate=(animate!==false);
  S.frames=[]; S.t=0; S.inertiaHist=[]; S.running=true; S.playing=S._animate;
  syncPlayBtn();
  _seenRun++; receiveFrame._last=null;
  S.cmp=null; S.animEnd=null; S.settlePending=false;
  $('algoTitle').textContent=S.algo;
  S.backend.run(S.algo, JSON.stringify(S.params));
  clearTimeout(run._wd);
  run._wd=setTimeout(()=>{ if(!S.frames.length)
    $('note').textContent='No frames received from backend — please report this'; },2500);
}
/** Append a frame to the buffer; in non-animate mode jump straight to the end
 *  so the settled result is shown without playing. */
function onFrame(fr){
  S.frames.push(fr);
  if(fr.metrics && typeof fr.metrics.inertia==='number') S.inertiaHist.push(fr.metrics.inertia);
  if(!S._animate) S.t=S.frames.length-1;
}

let _lastW=0, _lastH=0;
/** Animation loop: advance the playhead, refit on resize and redraw. */
function tick(now){
  if(canvas.clientWidth!==_lastW || canvas.clientHeight!==_lastH){
    _lastW=canvas.clientWidth; _lastH=canvas.clientHeight;
    if(_lastW>0 && _lastH>0){ resize();
      if(S.data && !S.data.empty){ fitView(); if(S.focus!=null) zoomToCluster(S.focus, true); } }
  }
  stepTween(now);
  if(!S.lastTick) S.lastTick=now;
  const dt=(now-S.lastTick)/1000; S.lastTick=now;
  if(S.playing && S.frames.length){
    S.t+=dt*S.fps; const end=S.frames.length-1;
    if(S.t>=end){ if(S.running) S.t=end; else if(S.loop) S.t=0;
      else { S.t=end; S.playing=false; syncPlayBtn(); } }
  }
  if(S.settlePending && !S.playing) settleOnCompare();
  draw();
  requestAnimationFrame(tick);
}
/** Return the buffered frame nearest index i, clamped to range. */
function frameAt(i){ return S.frames[Math.max(0,Math.min(S.frames.length-1,i))]; }

/** Render the current frame: axes, points, centroids and overlays. */
function draw(){
  const w=canvas.clientWidth,h=canvas.clientHeight;
  ctx.clearRect(0,0,w,h);
  if(EXPORT && !S.exp.transparent){ ctx.fillStyle=THEME.bg; ctx.fillRect(0,0,w,h); }
  if(!S.data||S.data.empty||!S.data.xy||!S.data.xy.length) return;

  const A=S.frames.length?frameAt(Math.floor(S.t)):null;
  drawFrame(A);
  if(EXPORT || !A) return;
  updateHud(A);
  drawInset(A);
  drawEquation(A);
}
 /**
 * Render the axes, particles and centroids of one frame.
 * @param {?Object} A The frame currently on screen, or null.
 */
function drawFrame(A){
  const P=S.data.xy, n=S.data.n;
  ctx.save();
  drawAxes();
  if(!A || !A.labels || A.labels.length!==n){
    drawPoints(P,new Array(n).fill(-1)); ctx.restore(); return;
  }
  const i0=Math.floor(S.t),f=S.t-i0,i1=Math.min(i0+1,S.frames.length-1);
  const B=frameAt(i1),labels=A.labels;
  let pos=P;
  if(A.positions){ pos=A.positions;
    if(B.positions && B.positions.length===A.positions.length) pos=lerpPts(A.positions,B.positions,f); }
  if(A.extra && A.extra.som_nodes) drawSom(A,B,f);
  drawPoints(pos,labels);
  let cen=A.centroids;
  if(cen && B.centroids && B.centroids.length===cen.length) cen=lerpPts(cen,B.centroids,f);
  if(cen) drawCentroids(cen);
  ctx.restore();
}

/**
 * Unicode replacements for the LaTeX commands the engine emits.
 * @type {Object<string,string>}
 */
const TEX_SYMBOLS = {
  alpha:'α', beta:'β', gamma:'γ', delta:'δ', epsilon:'ϵ', varepsilon:'ε',
  zeta:'ζ', eta:'η', theta:'θ', kappa:'κ', lambda:'λ', mu:'μ', nu:'ν',
  xi:'ξ', rho:'ρ', sigma:'σ', tau:'τ', phi:'φ', chi:'χ', psi:'ψ', omega:'ω',
  pi:'π', Gamma:'Γ', Delta:'Δ', Theta:'Θ', Lambda:'Λ', Xi:'Ξ', Pi:'Π',
  Sigma:'Σ', Phi:'Φ', Psi:'Ψ', Omega:'Ω',
  cdot:'·', times:'×', div:'÷', pm:'±', ast:'∗',
  le:'≤', leq:'≤', ge:'≥', geq:'≥', ne:'≠', neq:'≠', approx:'≈', equiv:'≡',
  in:'∈', notin:'∉', subset:'⊂', subseteq:'⊆', cup:'∪', cap:'∩',
  to:'→', rightarrow:'→', Rightarrow:'⇒', leftarrow:'←', gets:'←',
  Leftarrow:'⇐', iff:'⟺', mapsto:'↦', propto:'∝',
  infty:'∞', partial:'∂', nabla:'∇', forall:'∀', exists:'∃',
  ldots:'…', dots:'…', cdots:'⋯', mid:'∣', ell:'ℓ', prime:'′',
};
/**
 * LaTeX commands rendered upright, as operator names rather than variables.
 * @type {Object<string,string>}
 */
const TEX_OPS = {
  sum:'∑', prod:'∏', int:'∫', min:'min', max:'max', arg:'arg', exp:'exp',
  log:'log', ln:'ln', det:'det', sin:'sin', cos:'cos', tan:'tan',
  argmin:'arg min', argmax:'arg max',
};

/**
 * Typeset a LaTeX fragment as HTML.
 *
 * A deliberately small subset — fractions, super/subscripts, roots, norms,
 * greek letters, operator names and the usual relation symbols — which is
 * everything the engine's worked examples use. It is inlined rather than
 * pulled from KaTeX or MathJax so the view keeps working with no network and
 * no bundled third-party assets.
 *
 * @param {string} src LaTeX source without surrounding delimiters.
 * @returns {string} HTML markup wrapped in a `.ltx` span.
 */
function renderLatex(src){
  const s=String(src==null?'':src);
  let i=0;
  function group(stop){
    let out='';
    while(i<s.length){
      const ch=s[i];
      if(stop && ch===stop){ i++; break; }
      if(ch==='}'){ i++; continue; }
      if(ch==='{'){ i++; out+='<span class="lgrp">'+group('}')+'</span>'; continue; }
      if(ch==='\\'){ out+=command(); continue; }
      if(ch==='^'||ch==='_'){ i++;
        out+=`<${ch==='^'?'sup':'sub'}>${atom()}</${ch==='^'?'sup':'sub'}>`; continue; }
      if(ch==='$'){ i++; continue; }
      i++;
      out+=/[A-Za-z]/.test(ch) ? `<i>${esc(ch)}</i>` : esc(ch);
    }
    return out;
  }
  function atom(){
    if(s[i]==='{'){ i++; return group('}'); }
    if(s[i]==='\\') return command();
    const c=s[i++]||'';
    return /[A-Za-z]/.test(c) ? `<i>${esc(c)}</i>` : esc(c);
  }
  function command(){
    i++;
    const m=/^[A-Za-z]+/.exec(s.slice(i));
    if(!m){
      const c=s[i++]||'';
      if(c==='|') return '‖';
      if(c==='{'||c==='}') return esc(c);
      if(c===','||c===';'||c===' '||c==='!') return '<span class="lthin"></span>';
      if(c==='\\') return '<br>';
      return esc(c);
    }
    const name=m[0]; i+=name.length;
    while(s[i]===' ') i++;
    if(name==='frac'){
      const a=atom(), b=atom();
      return `<span class="lfrac"><span class="lnum">${a}</span>`+
             `<span class="lden">${b}</span></span>`;
    }
    if(name==='sqrt') return `<span class="lroot">${atom()}</span>`;
    if(name==='text'||name==='mathrm'||name==='mathcal'||name==='mathbf'||
       name==='operatorname') return `<span class="lup">${atom()}</span>`;
    if(name==='left'||name==='right'){
      const c=s[i++]||''; return c==='.'?'':esc(c);
    }
    if(name==='quad') return '<span class="lquad"></span>';
    if(name==='qquad') return '<span class="lquad"></span><span class="lquad"></span>';
    if(TEX_OPS[name]) return `<span class="lup lop">${TEX_OPS[name]}</span>`;
    if(TEX_SYMBOLS[name]) return `<span class="lup">${TEX_SYMBOLS[name]}</span>`;
    return `<span class="lup">${esc(name)}</span>`;
  }
  return `<span class="ltx">${group(null)}</span>`;
}
/**
 * Typeset mixed prose and maths, where maths is delimited by `$…$`.
 * @param {string} src Text with optional `$…$` spans.
 * @returns {string} HTML markup.
 */
function renderMixed(src){
  const parts=String(src==null?'':src).split('$');
  return parts.map((p,i)=>i%2 ? renderLatex(p) : esc(p)).join('');
}

/** Render the equation box for the current frame (formula + real numbers). */
function drawEquation(A){
  const box=$('eqbox'), chip=$('eqShow');
  const d = A && A.extra && A.extra.equation;
  if(!box) return;
  if(!d || !S.eqOn){
    box.classList.remove('show');
    if(chip) chip.classList.toggle('show', !!(d && !S.eqOn));
    return;
  }
  if(chip) chip.classList.remove('show');
  box.classList.add('show');
  box.classList.toggle('collapsed', S.eqCollapsed);
  $('eqTitle').textContent=d.title||'Worked example';
  if(S.eqCollapsed) return;
  const key=JSON.stringify([d.title,d.formula,d.lines,d.result,d.note]);
  if(key===drawEquation._key) return;
  drawEquation._key=key;
  $('eqFormula').innerHTML=renderLatex(d.formula||'');
  const body=$('eqBody');
  let html=(d.lines||[]).map(row=>
    `<div class="eqrow"><span class="lhs">${renderLatex(row[0]||'')}</span>`+
    `<span class="sub">${renderMixed(row[1]||'')}</span>`+
    `<span class="val">${renderMixed(row[2]||'')}</span></div>`).join('');
  if(d.result) html+=`<div class="eqres"><span>${renderMixed(d.result[0])}</span>`+
    `<b>${renderMixed(d.result[1])}</b></div>`;
  if(d.note) html+=`<div class="eqnote">${esc(d.note)}</div>`;
  body.innerHTML=html;
}

/** Resolve a palette keyword ('accent', 'warn', 'bad', 'good') to a colour. */
function themeColor(name){
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue('--' + name).trim();
  return v || THEME.accent;
}
/** True when every leaf under a node carries the same cluster id. */
function uniformLabel(leaves, leafLabels){
  if(!leafLabels || !leaves.length) return null;
  const c = leafLabels[leaves[0]];
  for(const l of leaves) if(leafLabels[l] !== c) return null;
  return c;
}
/** Size the inset canvas to its box and clear it; returns the CSS-pixel box. */
function insetSetup(){
  const w = icanvas.clientWidth, h = icanvas.clientHeight;
  if(icanvas.width !== Math.round(w*DPR) || icanvas.height !== Math.round(h*DPR)){
    icanvas.width = Math.round(w*DPR); icanvas.height = Math.round(h*DPR);
  }
  ictx.setTransform(DPR,0,0,DPR,0,0);
  ictx.clearRect(0,0,w,h);
  ictx.font=uiFont(0.72);
  return {w,h};
}
/** Draw the inset frame: axes box, optional labels, returns the plot rect. */
function insetAxes(w,h,opts){
  const o = opts||{};
  const fs = uiSize();
  const L = o.left!=null?o.left:Math.max(28, fs*2.5), R = o.right!=null?o.right:10;
  const T = Math.max(10, fs*0.8);
  const B = (o.ylabel||o.xlabel) ? Math.max(22, fs*1.8) : Math.max(14, fs*1.2);
  const r = {x:L, y:T, w:Math.max(10,w-L-R), h:Math.max(10,h-T-B)};
  ictx.strokeStyle=THEME.text; ictx.globalAlpha=.18; ictx.lineWidth=1;
  ictx.beginPath();
  ictx.moveTo(r.x, r.y); ictx.lineTo(r.x, r.y+r.h); ictx.lineTo(r.x+r.w, r.y+r.h);
  ictx.stroke(); ictx.globalAlpha=1;
  ictx.fillStyle=THEME.text; ictx.globalAlpha=.55;
  if(o.xlabel){ ictx.textAlign='right'; ictx.textBaseline='top';
    ictx.fillText(o.xlabel, r.x+r.w, r.y+r.h+6); }
  if(o.ylabel){ ictx.textAlign='left'; ictx.textBaseline='top';
    ictx.fillText(o.ylabel, 2, 1); }
  ictx.globalAlpha=1;
  return r;
}
/** Draw min/max tick labels on the inset y axis. */
function insetYTicks(r, lo, hi){
  ictx.fillStyle=THEME.text; ictx.globalAlpha=.5;
  ictx.textAlign='right'; ictx.textBaseline='middle';
  const fmt=(v)=>Math.abs(v)>=1000||(v!==0&&Math.abs(v)<0.01)
    ? v.toExponential(1) : (+v.toFixed(2)+'');
  ictx.fillText(fmt(hi), r.x-4, r.y+4);
  ictx.fillText(fmt(lo), r.x-4, r.y+r.h-4);
  ictx.globalAlpha=1;
}
/** Render the algorithm-specific detail box for the current frame. */
function drawInset(A){
  const box=$('inset'), btn=$('insetShow');
  const d = A && A.extra && A.extra.inset;
  if(!ictx || !d || !S.insetOn){
    if(box) box.classList.remove('show');
    if(btn) btn.classList.toggle('show', !!(d && !S.insetOn));
    return;
  }
  if(btn) btn.classList.remove('show');
  box.classList.add('show');
  box.classList.toggle('collapsed', S.insetCollapsed);
  $('insetTitle').textContent = d.title || 'Detail';
  $('insetSub').textContent = d.subtitle || '';
  if(S.insetCollapsed) return;
  const {w,h}=insetSetup();
  if(w<40||h<30) return;
  try{
    if(d.kind==='curve') insetCurve(d,w,h);
    else if(d.kind==='bars') insetBars(d,w,h);
    else if(d.kind==='dendrogram') insetDendro(d,w,h);
    else if(d.kind==='grid') insetGrid(d,w,h);
  }catch(e){
    ictx.fillStyle=THEME.text; ictx.globalAlpha=.6; ictx.textAlign='left';
    ictx.fillText('detail view unavailable', 8, 16); ictx.globalAlpha=1;
  }
}
/** Line-chart inset: one or two series, optional threshold line and bar strip. */
function insetCurve(d,w,h){
  const series=(d.series||[]).filter(s=>s.y&&s.y.length);
  const bars=(d.bars||[]).filter(b=>b.values&&b.values.length);
  const barH = bars.length ? 30 : 0;
  const r = insetAxes(w, h-barH, {xlabel:d.xlabel, ylabel:d.ylabel});
  if(!series.length){
    ictx.fillStyle=THEME.text; ictx.globalAlpha=.45; ictx.textAlign='center';
    ictx.fillText('collecting…', r.x+r.w/2, r.y+r.h/2); ictx.globalAlpha=1;
  }
  const left=series.filter(s=>s.axis!=='right'), right=series.filter(s=>s.axis==='right');
  const rng=(list)=>{ let lo=Infinity,hi=-Infinity;
    for(const s of list) for(const v of s.y) if(v!=null&&isFinite(v)){
      if(v<lo)lo=v; if(v>hi)hi=v; }
    if(!isFinite(lo)){lo=0;hi=1;} if(hi-lo<1e-12){hi=lo+1;} return [lo,hi]; };
  let [lo,hi]=rng(left.length?left:series);
  if(d.hline && d.hline.y!=null){ lo=Math.min(lo,d.hline.y); hi=Math.max(hi,d.hline.y); }
  const [rlo,rhi]=rng(right.length?right:[{y:[0,1]}]);
  const nmax=Math.max(...series.map(s=>s.y.length), 2);
  const px=(i)=>r.x + (nmax<2?0:(i/(nmax-1))*r.w);
  const py=(v,useR)=>useR ? r.y+r.h-((v-rlo)/(rhi-rlo))*r.h
                          : r.y+r.h-((v-lo)/(hi-lo))*r.h;
  if(d.hline && d.hline.y!=null){
    ictx.strokeStyle=themeColor(d.hline.color||'bad'); ictx.globalAlpha=.85;
    ictx.setLineDash([4,3]); ictx.lineWidth=1.2; ictx.beginPath();
    ictx.moveTo(r.x, py(d.hline.y)); ictx.lineTo(r.x+r.w, py(d.hline.y)); ictx.stroke();
    ictx.setLineDash([]);
    if(d.hline.label){ ictx.fillStyle=themeColor(d.hline.color||'bad');
      ictx.textAlign='right'; ictx.textBaseline='bottom';
      ictx.fillText(d.hline.label, r.x+r.w-2, py(d.hline.y)-2); }
    ictx.globalAlpha=1;
  }
  for(const s of series){
    const useR = s.axis==='right';
    ictx.strokeStyle=themeColor(s.color||'accent');
    ictx.globalAlpha=useR?.7:1; ictx.lineWidth=useR?1.1:1.8;
    if(useR) ictx.setLineDash([3,2]);
    ictx.beginPath(); let started=false;
    for(let i=0;i<s.y.length;i++){ const v=s.y[i];
      if(v==null||!isFinite(v)){ started=false; continue; }
      const X=px(i), Y=py(v,useR);
      if(started) ictx.lineTo(X,Y); else { ictx.moveTo(X,Y); started=true; } }
    ictx.stroke(); ictx.setLineDash([]);
    const last=s.y.length-1, lv=s.y[last];
    if(lv!=null&&isFinite(lv)){ ictx.fillStyle=themeColor(s.color||'accent');
      ictx.beginPath(); ictx.arc(px(last),py(lv,useR),2.6,0,6.283); ictx.fill(); }
    ictx.globalAlpha=1;
  }
  insetYTicks(r, lo, hi);
  let ly=r.y+2; const lh=Math.max(10, uiSize()*0.82);
  ictx.textAlign='left'; ictx.textBaseline='top';
  for(const s of series){ ictx.fillStyle=themeColor(s.color||'accent');
    ictx.globalAlpha=.9; ictx.fillText('— '+(s.label||''), r.x+5, ly); ly+=lh; }
  ictx.globalAlpha=1;
  if(bars.length) insetBarStrip(bars[0], r.x, h-barH+4, r.w, barH-10);
}
/** Small horizontal bar strip used under a curve (weights, sizes …). */
function insetBarStrip(bar, x, y, w, h){
  const vals=bar.values||[]; if(!vals.length) return;
  const mx=Math.max(...vals.map(v=>Math.abs(v)||0), 1e-9);
  const bw=Math.max(1.5, w/vals.length - 2);
  for(let i=0;i<vals.length;i++){
    const v=Math.abs(vals[i]||0), bh=Math.max(1,(v/mx)*h);
    ictx.fillStyle = bar.by_cluster ? colorFor(i) : themeColor('accent');
    ictx.globalAlpha=.85;
    ictx.fillRect(x + i*(w/vals.length), y+h-bh, bw, bh);
  }
  ictx.globalAlpha=.55; ictx.fillStyle=THEME.text;
  ictx.textAlign='left'; ictx.textBaseline='bottom';
  ictx.fillText(bar.label||'', x, y+h+9); ictx.globalAlpha=1;
}
/** Bar-chart inset: reachability plot, eigen spectrum, CF-leaf sizes. */
function insetBars(d,w,h){
  const vals=(d.values||[]).map(v=>(v==null||!isFinite(v))?null:v);
  const r=insetAxes(w,h,{xlabel:d.xlabel, ylabel:d.ylabel});
  if(!vals.length){ ictx.fillStyle=THEME.text; ictx.globalAlpha=.45;
    ictx.textAlign='center'; ictx.fillText('collecting…', r.x+r.w/2, r.y+r.h/2);
    ictx.globalAlpha=1; return; }
  let hi=-Infinity, lo=0;
  for(const v of vals) if(v!=null && v>hi) hi=v;
  if(d.hline && d.hline.y!=null) hi=Math.max(hi, d.hline.y);
  if(!isFinite(hi)||hi<=0) hi=1;
  const step=r.w/vals.length, bw=Math.max(1, step-(step>4?1:0));
  for(let i=0;i<vals.length;i++){
    const v=vals[i]; if(v==null) continue;
    const bh=Math.max(0.5,(v/hi)*r.h);
    const cl = d.bar_clusters ? d.bar_clusters[i] : null;
    ictx.fillStyle = (cl!=null) ? colorFor(cl)
      : (d.highlight!=null && i<=d.highlight) ? themeColor('accent') : THEME.noise;
    ictx.globalAlpha = (d.cursor!=null && i>d.cursor) ? .25 : .9;
    ictx.fillRect(r.x+i*step, r.y+r.h-bh, bw, bh);
  }
  ictx.globalAlpha=1;
  if(d.hline && d.hline.y!=null){
    const y=r.y+r.h-(d.hline.y/hi)*r.h;
    ictx.strokeStyle=themeColor(d.hline.color||'bad'); ictx.setLineDash([4,3]);
    ictx.lineWidth=1.2; ictx.beginPath(); ictx.moveTo(r.x,y); ictx.lineTo(r.x+r.w,y);
    ictx.stroke(); ictx.setLineDash([]);
    if(d.hline.label){ ictx.fillStyle=themeColor(d.hline.color||'bad');
      ictx.textAlign='right'; ictx.textBaseline='bottom';
      ictx.fillText(d.hline.label, r.x+r.w-2, y-2); }
  }
  if(d.vline && d.vline.x!=null){
    const x=r.x+(d.vline.x/vals.length)*r.w;
    ictx.strokeStyle=themeColor(d.vline.color||'bad'); ictx.setLineDash([4,3]);
    ictx.lineWidth=1.2; ictx.beginPath(); ictx.moveTo(x,r.y); ictx.lineTo(x,r.y+r.h);
    ictx.stroke(); ictx.setLineDash([]);
    if(d.vline.label){ ictx.fillStyle=themeColor(d.vline.color||'bad');
      ictx.textAlign='left'; ictx.textBaseline='top';
      ictx.fillText(' '+d.vline.label, x, r.y); }
  }
  if(d.cursor!=null && d.cursor<vals.length){
    const x=r.x+(d.cursor/vals.length)*r.w;
    ictx.strokeStyle=THEME.text; ictx.globalAlpha=.5; ictx.lineWidth=1;
    ictx.beginPath(); ictx.moveTo(x,r.y); ictx.lineTo(x,r.y+r.h); ictx.stroke();
    ictx.globalAlpha=1;
  }
  const line=(d.series||[])[0];
  if(line && line.y && line.y.length>1){
    const mx=Math.max(...line.y);
    ictx.strokeStyle=themeColor(line.color||'warn'); ictx.globalAlpha=.8;
    ictx.lineWidth=1.3; ictx.setLineDash([3,2]); ictx.beginPath();
    line.y.forEach((v,i)=>{ const X=r.x+(i/(line.y.length-1))*r.w,
      Y=r.y+r.h-((v/(mx||1))*r.h); i?ictx.lineTo(X,Y):ictx.moveTo(X,Y); });
    ictx.stroke(); ictx.setLineDash([]); ictx.globalAlpha=1;
  }
  insetYTicks(r, lo, hi);
}
/** Build leaf positions and heights for a scipy-style merge list. */
function buildDendro(d){
  const n=d.n_leaves||0, merges=d.merges||[];
  const kids=new Map(); merges.forEach((m,i)=>kids.set(n+i,[m[0],m[1]]));
  const consumed=new Set();
  for(const [a,b] of kids.values()){ consumed.add(a); consumed.add(b); }
  const roots=[];
  for(let i=0;i<n+merges.length;i++)
    if(!consumed.has(i) && (i<n || kids.has(i))) roots.push(i);
  const x=new Map(), leaves=new Map(); let slot=0;
  const stack=[];
  for(const r0 of roots){
    stack.length=0; stack.push([r0,false]);
    while(stack.length){
      const [id,done]=stack.pop();
      if(!kids.has(id)){ x.set(id,slot++); leaves.set(id,[id]); continue; }
      if(!done){ stack.push([id,true]);
        const [a,b]=kids.get(id); stack.push([b,false]); stack.push([a,false]); }
      else { const [a,b]=kids.get(id);
        x.set(id,(x.get(a)+x.get(b))/2);
        leaves.set(id, leaves.get(a).concat(leaves.get(b))); }
    }
  }
  const hgt=new Map(); merges.forEach((m,i)=>hgt.set(n+i, m[2]));
  return {n, kids, roots, x, hgt, leaves, slots:Math.max(slot,1)};
}
/** Dendrogram / condensed-tree inset drawn from the accumulated merges. */
function insetDendro(d,w,h){
  const r=insetAxes(w,h,{xlabel:'leaves', ylabel:d.ylabel||'distance'});
  const T=buildDendro(d);
  if(!T.n){ return; }
  let hmax=0; for(const v of T.hgt.values()) if(v>hmax) hmax=v;
  if(!(hmax>0)) hmax=1;
  const X=(i)=>r.x + ((i+0.5)/T.slots)*r.w;
  const Y=(v)=>r.y + r.h - (v/hmax)*r.h*0.94;
  const ll=d.leaf_labels;
  const colOf=(id)=>{ const c=uniformLabel(T.leaves.get(id)||[], ll);
    return (c==null||c<0)?THEME.noise:colorFor(c); };
  ictx.lineWidth=1.2;
  for(const [id,[a,b]] of T.kids){
    const ya=T.kids.has(a)?Y(T.hgt.get(a)):Y(0), yb=T.kids.has(b)?Y(T.hgt.get(b)):Y(0);
    const yt=Y(T.hgt.get(id)), xa=X(T.x.get(a)), xb=X(T.x.get(b));
    ictx.strokeStyle=colOf(id);
    ictx.globalAlpha = colOf(id)===THEME.noise ? .45 : .95;
    ictx.beginPath();
    ictx.moveTo(xa,ya); ictx.lineTo(xa,yt); ictx.lineTo(xb,yt); ictx.lineTo(xb,yb);
    ictx.stroke();
  }
  ictx.globalAlpha=1;
  for(let i=0;i<T.n;i++){ if(!T.x.has(i)) continue;
    const c=(ll&&ll[i]!=null)?ll[i]:-1;
    ictx.fillStyle = c<0?THEME.noise:colorFor(c); ictx.globalAlpha=c<0?.5:.95;
    ictx.fillRect(X(T.x.get(i))-1, r.y+r.h-2.5, 2, 2.5); }
  ictx.globalAlpha=1;
  if(d.cut!=null){
    const heights=[...T.hgt.values()].sort((a,b)=>b-a);
    const idx=(d.target!=null?d.target:d.cut)-1;
    if(idx>=0 && idx<heights.length){
      const y=Y((heights[idx]+(heights[idx+1]!=null?heights[idx+1]:0))/2);
      ictx.strokeStyle=themeColor('bad'); ictx.setLineDash([4,3]); ictx.lineWidth=1.1;
      ictx.globalAlpha=.9; ictx.beginPath();
      ictx.moveTo(r.x,y); ictx.lineTo(r.x+r.w,y); ictx.stroke();
      ictx.setLineDash([]); ictx.textAlign='left'; ictx.textBaseline='bottom';
      ictx.fillStyle=themeColor('bad');
      ictx.fillText(' cut · '+d.cut+' groups', r.x, y-1); ictx.globalAlpha=1;
    }
  }
  insetYTicks(r, 0, hmax);
}
/** Grid/heatmap inset — the SOM U-matrix in map space. */
function insetGrid(d,w,h){
  const rows=d.rows||1, cols=d.cols||1, vals=d.values||[];
  const pad=10, availW=w-2*pad, availH=h-2*pad-12;
  const cs=Math.max(4, Math.min(availW/cols, availH/rows));
  const x0=(w-cs*cols)/2, y0=pad+(availH-cs*rows)/2;
  let lo=Infinity, hi=-Infinity;
  for(const v of vals){ if(v==null||!isFinite(v)) continue;
    if(v<lo)lo=v; if(v>hi)hi=v; }
  if(!isFinite(lo)){ lo=0; hi=1; }
  if(hi-lo<1e-12) hi=lo+1;
  for(let rI=0;rI<rows;rI++) for(let c=0;c<cols;c++){
    const i=rI*cols+c, v=vals[i];
    const t=(v==null||!isFinite(v))?0:(v-lo)/(hi-lo);
    const x=x0+c*cs, y=y0+rI*cs;
    ictx.fillStyle=THEME.text; ictx.globalAlpha=0.08+0.72*t;
    ictx.fillRect(x,y,cs-1,cs-1);
    const cl=d.cell_labels?d.cell_labels[i]:null;
    if(cl!=null){ ictx.globalAlpha=.95; ictx.fillStyle=colorFor(cl);
      ictx.beginPath(); ictx.arc(x+cs/2,y+cs/2,Math.max(1.4,cs*0.16),0,6.283); ictx.fill(); }
  }
  ictx.globalAlpha=1;
  ictx.fillStyle=THEME.text; ictx.globalAlpha=.5;
  ictx.textAlign='left'; ictx.textBaseline='bottom';
  ictx.fillText('light = similar neighbours · dark = cluster boundary', pad, h-3);
  ictx.globalAlpha=1;
}

/** Draw the particle scatter, depth-sorted in 3-D. */
function drawPoints(pos,labels){
  const r=pointRadius();
  if(curDims()===3){
    const sc=new Array(pos.length), vis=[];
    for(let i=0;i<pos.length;i++){ if(S.hidden.has(labels[i])) continue;
      sc[i]=screen(pos[i]); vis.push(i); }
    vis.sort((a,b)=>{
      const fa=isDimmed(labels[a])?0:1, fb=isDimmed(labels[b])?0:1;
      return fa!==fb ? fa-fb : sc[a][2]-sc[b][2];
    });
    for(const i of vis){ const c=labels[i];
      ctx.globalAlpha=((c<0)?0.4:0.85)*(isDimmed(c)?DIM_ALPHA:1); ctx.fillStyle=colorFor(c);
      ctx.beginPath(); ctx.arc(sc[i][0],sc[i][1],r,0,6.283); ctx.fill(); }
    ctx.globalAlpha=1;
  } else {
    const groups=new Map();
    for(let i=0;i<pos.length;i++){ const c=labels[i]; if(S.hidden.has(c)) continue;
      const col=colorFor(c), dim=isDimmed(c), key=col+'|'+(dim?'1':'0');
      let g=groups.get(key);
      if(!g){ g={col, dim, idxs:[]}; groups.set(key,g); }
      g.idxs.push(i); }
    const order=[...groups.values()].sort((a,b)=>(a.dim?0:1)-(b.dim?0:1));
    for(const g of order){
      ctx.fillStyle=g.col;
      ctx.globalAlpha=((g.col===THEME.noise)?0.45:0.88)*(g.dim?DIM_ALPHA:1);
      ctx.beginPath();
      for(const i of g.idxs){ const s=screen(pos[i]); ctx.moveTo(s[0]+r,s[1]); ctx.arc(s[0],s[1],r,0,6.283); }
      ctx.fill();
    }
    ctx.globalAlpha=1;
  }
  if(S.hoverIdx>=0 && S.hoverIdx<pos.length){
    const s=screen(pos[S.hoverIdx]);
    ctx.strokeStyle=THEME.text; ctx.lineWidth=2; ctx.beginPath(); ctx.arc(s[0],s[1],r+3,0,6.283); ctx.stroke();
  }
}
/** Draw cluster centroids as ringed markers. */
function drawCentroids(cen){
  const order=cen.map((_,k)=>k).filter(k=>cen[k] && !S.hidden.has(k));
  if(curDims()===3){
    const d={};
    for(const k of order) d[k]=screen(cen[k]);
    order.sort((a,b)=>d[a][2]-d[b][2]);
  }
  order.sort((a,b)=>(isDimmed(a)?0:1)-(isDimmed(b)?0:1));
  const R=Math.max(2, S.ui.centSize), halo=R*1.69, ring=R*1.38;
  for(const k of order){
    const s=screen(cen[k]),x=s[0],y=s[1],col=colorFor(k);
    const a=isDimmed(k)?DIM_ALPHA:1;
    ctx.beginPath(); ctx.arc(x,y,halo,0,6.283); ctx.fillStyle=col; ctx.globalAlpha=.22*a; ctx.fill();
    ctx.globalAlpha=a;
    ctx.beginPath(); ctx.arc(x,y,R,0,6.283); ctx.fillStyle=col; ctx.fill();
    ctx.lineWidth=Math.max(1.5,R*0.38); ctx.strokeStyle=THEME.bg; ctx.stroke();
    ctx.lineWidth=1.5; ctx.strokeStyle=THEME.text; ctx.globalAlpha=.8*a;
    ctx.beginPath(); ctx.arc(x,y,ring,0,6.283); ctx.stroke(); ctx.globalAlpha=1;
  }
}
/** Draw the self-organising-map neuron grid overlay. */
function drawSom(A,B,f){
  let nodes=A.extra.som_nodes;
  if(B.extra && B.extra.som_nodes && B.extra.som_nodes.length===nodes.length)
    nodes=lerpPts(nodes,B.extra.som_nodes,f);
  const sc=nodes.map(screen), edges=A.extra.som_edges||[];
  ctx.strokeStyle=THEME.text; ctx.globalAlpha=.28; ctx.lineWidth=1.2; ctx.beginPath();
  for(const [a,b] of edges){ ctx.moveTo(sc[a][0],sc[a][1]); ctx.lineTo(sc[b][0],sc[b][1]); }
  ctx.stroke(); ctx.globalAlpha=1; ctx.fillStyle=THEME.text;
  for(const s of sc){ ctx.beginPath(); ctx.arc(s[0],s[1],3.2,0,6.283); ctx.fill(); }
}
/**
 * Human label for display axis `i` (0=x, 1=y, 2=z), based on the projection.
 * @param {number} i Axis index.
 * @returns {string} e.g. "PC1 (63%)", "t-SNE 2", or an element name for "None".
 */
function axisName(i){
  const d=S.data||{};
  if(d.axis_labels && d.axis_labels[i]) return d.axis_labels[i];
  const p=d.projection||'PCA';
  if(p==='PCA'){ const vr=d.var_ratio, v=vr&&vr[i];
    return 'PC'+(i+1)+((v!=null&&v===v)?` (${(v*100).toFixed(0)}%)`:''); }
  return p+' '+(i+1);
}
/** True when the axes are raw element channels rather than projected components. */
function axesAreElements(){
  const d=S.data||{};
  return (d.projection==='None') && !!(d.axis_labels && d.axis_labels.length);
}
/** Draw one axis caption, formatting it as an element when appropriate. */
 /**
 * Draw tick marks and values along the 2-D axes.
 *
 * The ticks are derived from the visible data range, so zooming changes the
 * numbers rather than leaving the frame looking identical.
 *
 * @param {number} w Canvas width in CSS pixels.
 * @param {number} h Canvas height in CSS pixels.
 * @param {number} ox Screen x of the vertical axis.
 * @param {number} oy Screen y of the horizontal axis.
 */
function drawTicks(w, h, ox, oy){
  const size=Math.max(7, uiSize()*0.68);
  ctx.font=(size.toFixed(1))+'px '+uiFontStack();
  ctx.strokeStyle=THEME.text; ctx.fillStyle=THEME.text; ctx.lineWidth=1;

  const xs=niceTicks(ux(0), ux(w), 8);
  ctx.textAlign='center'; ctx.textBaseline='top';
  const yLab=Math.min(h-size-3, oy+5);
  for(const v of xs.values){
    const px=wx(v);
    if(px<14 || px>w-14) continue;
    ctx.globalAlpha=.30;
    ctx.beginPath(); ctx.moveTo(px, oy-3); ctx.lineTo(px, oy+3); ctx.stroke();
    if(v===0) continue;
    ctx.globalAlpha=.55; ctx.fillText(fmtTick(v, xs.step), px, yLab);
  }

  const ys=niceTicks(uy(h), uy(0), 6);
  ctx.textAlign='left'; ctx.textBaseline='middle';
  const xLab=Math.min(w-4, ox+6);
  for(const v of ys.values){
    const py=wy(v);
    if(py<10 || py>h-10) continue;
    ctx.globalAlpha=.30;
    ctx.beginPath(); ctx.moveTo(ox-3, py); ctx.lineTo(ox+3, py); ctx.stroke();
    if(v===0) continue;
    ctx.globalAlpha=.55; ctx.fillText(fmtTick(v, ys.step), xLab, py);
  }
  ctx.globalAlpha=1; ctx.textAlign='start'; ctx.textBaseline='alphabetic';
}
/**
 * Draw one axis name, rendering it as an element when the axes are elements.
 *
 * @param {number} i Axis index: 0 = x, 1 = y, 2 = z.
 * @param {number} x Screen x of the caption.
 * @param {number} y Screen y of the caption.
 * @param {string} align Canvas text alignment.
 */
function drawAxisCaption(i,x,y,align){
  const size=Math.max(8, uiSize()*0.85);
  if(axesAreElements()) drawElementLabel(ctx, axisName(i), x, y, size, align);
  else { ctx.textAlign=align; ctx.fillText(axisName(i), x, y); }
}
 /**
 * Draw the 3-D axis triad with graduated ticks.
 *
 * Each arm is extended to a whole number of round steps rather than a fixed
 * length, so zooming changes the tick values and the graduations rather than
 * leaving an identical-looking cross on screen. The arm covers roughly the
 * same fraction of the canvas at any zoom, so it never collapses to a stub or
 * runs off the edge.
 */
function drawAxes3(){
  const c=S.v3.center||[0,0,0], o=screen(c);
  const px=0.38*Math.min(paneW(), canvas.clientHeight);
  const reach=px/(S.v3.scale || 1);
  const t=niceTicks(0, reach, 4);
  const step=t.step||reach||1;
  const n=Math.max(1, Math.min(12, Math.floor(reach/step)));
  const L=step*n;
  const tickPx=Math.max(3, px*0.018);
  const small=Math.max(7, uiSize()*0.62);

  for(let i=0;i<3;i++){
    const end=c.slice(); end[i]=c[i]+L;
    const s=screen(end);
    ctx.globalAlpha=.35; ctx.strokeStyle=THEME.text; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(o[0],o[1]); ctx.lineTo(s[0],s[1]); ctx.stroke();

    const dx=s[0]-o[0], dy=s[1]-o[1], len=Math.hypot(dx,dy)||1;
    const nx=-dy/len*tickPx, ny=dx/len*tickPx;
    ctx.font=(small.toFixed(1))+'px '+uiFontStack();
    ctx.textAlign='center'; ctx.textBaseline='middle';
    for(let k=1;k<=n;k++){
      const p=c.slice(); p[i]=c[i]+step*k;
      const q=screen(p);
      ctx.globalAlpha=.30;
      ctx.beginPath(); ctx.moveTo(q[0]-nx,q[1]-ny); ctx.lineTo(q[0]+nx,q[1]+ny); ctx.stroke();
      if(k===n) continue;
      ctx.globalAlpha=.45; ctx.fillStyle=THEME.text;
      ctx.fillText(fmtTick(c[i]+step*k, step), q[0]+nx*2.1, q[1]+ny*2.1);
    }

    ctx.globalAlpha=.75; ctx.fillStyle=THEME.text;
    ctx.font=uiFont(0.85);
    drawAxisCaption(i, s[0], s[1]-4, 'center');
  }
  ctx.globalAlpha=1; ctx.textAlign='start'; ctx.textBaseline='alphabetic';
}
/** Draw labelled X/Y (and Z in 3-D) axes. */
function drawAxes(){
  ctx.save(); ctx.font=uiFont(0.85);
  if(curDims()===3){
    drawAxes3();
  } else {
    const w=canvas.clientWidth, h=canvas.clientHeight;
    const ox=Math.max(0.5, Math.min(w-0.5, wx(0)));
    const oy=Math.max(0.5, Math.min(h-0.5, wy(0)));
    ctx.globalAlpha=.28; ctx.strokeStyle=THEME.text; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(0,oy); ctx.lineTo(w,oy); ctx.moveTo(ox,0); ctx.lineTo(ox,h); ctx.stroke();
    drawTicks(w, h, ox, oy);
    ctx.globalAlpha=.7; ctx.fillStyle=THEME.text;
    ctx.textBaseline='bottom'; drawAxisCaption(0, w-8, oy-5, 'right');
    ctx.textBaseline='top';    drawAxisCaption(1, ox+6, 8+uiSize()*0.6, 'left');
  }
  ctx.restore(); ctx.globalAlpha=1; ctx.textBaseline='alphabetic';
}
/** Return the point radius — the Appearance slider, or auto by particle count. */
function pointRadius(){
  if(S.ui.pointSize>0) return S.ui.pointSize;
  return S.data.n>1600?2.0:(S.data.n>800?2.6:3.3);
}

/**
 * Split an element key into (symbol, mass), matching the clustering figures'
 * parser: prefix ('107Ag'), suffix ('Ag107' / 'Ag-107') or a bare symbol.
 * @param {string} label Raw element key.
 * @returns {[string, string|null]} Symbol (with any charge) and mass number.
 */
function parseElementLabel(label){
  const text=String(label||'').trim();
  if(!text) return ['', null];
  let m=/^\s*(\d+)\s*([A-Za-z][A-Za-z]?)\s*([+\-]\d*)?\s*$/.exec(text);
  if(m) return [m[2], m[1]];
  m=/^\s*([A-Za-z][A-Za-z]?)\s*(?:[-\s]?\s*(\d+))?\s*([+\-]\d*)?\s*$/.exec(text);
  if(m) return [m[1]+(m[3]||''), m[2]||null];
  m=/^\s*([A-Za-z][A-Za-z]?)/.exec(text);
  return m ? [m[1], null] : [text, null];
}
/** Escape text for safe insertion into innerHTML. */
function esc(s){ return String(s).replace(/[&<>"]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
/**
 * Format one element key for the current label mode, as HTML.
 * 'Symbol' → Ag · 'Mass + Symbol' → 107Ag · 'Atomic Notation' → <sup>107</sup>Ag
 * @param {string} key Element key, possibly a comma/plus separated combination.
 * @returns {string} HTML-safe formatted label.
 */
function elementLabelHTML(key){
  const mode=S.ui.labelMode;
  if(mode==='Mass + Symbol') return esc(key);
  return String(key).split(/(\s*[,+]\s*)/).map(tok=>{
    if(!tok.trim() || /^[\s,+]+$/.test(tok)) return esc(tok);
    const [sym,mass]=parseElementLabel(tok);
    if(mode==='Atomic Notation' && mass) return '<sup>'+esc(mass)+'</sup>'+esc(sym);
    return esc(sym||tok);
  }).join('');
}
/** Plain-text form of an element label for the current mode (canvas use). */
function elementLabelText(key){
  const mode=S.ui.labelMode;
  if(mode==='Mass + Symbol') return String(key);
  return String(key).split(/(\s*[,+]\s*)/).map(tok=>{
    if(!tok.trim() || /^[\s,+]+$/.test(tok)) return tok;
    const [sym,mass]=parseElementLabel(tok);
    return (mode==='Atomic Notation' && mass) ? mass+sym : (sym||tok);
  }).join('');
}
/**
 * Draw an element label on a canvas, raising the mass number in Atomic
 * Notation mode (canvas has no <sup>, so the digits are drawn smaller and up).
 * @param {CanvasRenderingContext2D} c Target context.
 * @param {string} key Element key.
 * @param {number} x Anchor x.
 * @param {number} y Baseline y.
 * @param {number} size Base font size in px.
 * @param {string} align 'left' | 'right' | 'center'.
 */
function drawElementLabel(c, key, x, y, size, align){
  const mode=S.ui.labelMode;
  const [sym,mass]=parseElementLabel(key);
  if(mode!=='Atomic Notation' || !mass){
    c.textAlign=align||'left';
    c.fillText(elementLabelText(key), x, y);
    return;
  }
  const small=Math.max(6, size*0.68), stack=uiFontStack();
  c.font=`${small}px ${stack}`; const mw=c.measureText(mass).width;
  c.font=`${size}px ${stack}`;  const sw=c.measureText(sym).width;
  let sx=x;
  if(align==='right') sx=x-(mw+sw);
  else if(align==='center') sx=x-(mw+sw)/2;
  c.textAlign='left';
  c.font=`${small}px ${stack}`; c.fillText(mass, sx, y-size*0.34);
  c.font=`${size}px ${stack}`;  c.fillText(sym, sx+mw, y);
}
/** Linearly interpolate between two arrays of N-D points. */
function lerpPts(a,b,f){ const o=new Array(a.length);
  for(let i=0;i<a.length;i++){
    const ai=a[i],bi=b[i];
    if(!ai || !bi){ o[i]=ai||bi||null; continue; }
    const m=ai.length,r=new Array(m);
    for(let j=0;j<m;j++) r[j]=ai[j]+((bi[j]||0)-ai[j])*f; o[i]=r; } return o; }

/** Update the note, cluster-count chips and legend. */
function updateHud(fr){
  $('note').textContent=fr.note||'';
  const m=fr.metrics||{};
  setChip('cK', m.n_clusters!=null?m.n_clusters:'–');
  setChip('cNoise', m.n_noise!=null?m.n_noise:'–');
  buildLegend(fr.labels);
}
/** Set a metric chip's text. */
function setChip(id,v){ const el=$(id); if(el) el.textContent=v; }
/**
 * Compute the two dominant elements of a cluster from mean raw composition,
 * mirroring the label style of the matplotlib figure legend.
 * @param {number[]} labels Per-point cluster ids for the current frame.
 * @param {number} c Cluster id to summarise.
 * @returns {string} Up to two element symbols joined by '·', or ''.
 */
 /**
 * Render one legend token, which may be the overflow marker rather than an
 * element.
 *
 * @param {string} tok An element key, or a '+N…' overflow count.
 * @returns {string} HTML for the token.
 */
function elementTokenHTML(tok){
  return /^\+\d/.test(tok) ? esc(tok) : elementLabelHTML(tok);
}
/**
 * The elements that dominate a cluster's mean composition.
 *
 * Applies the same limits as the ② Cluster legends: elements contributing less
 * than ``S.ui.minPct`` are dropped, the top ``S.ui.maxIso`` are kept, and any
 * remainder is reported as a '+N…' token.
 *
 * @param {number[]} labels Per-point cluster ids for the current frame.
 * @param {number} c Cluster id.
 * @returns {string[]} Element keys in descending abundance, plus any overflow
 *   token. Empty when the cluster holds no signal.
 */
function clusterTopElements(labels, c){
  const raw=S.data&&S.data.raw, els=S.data&&S.data.elements;
  if(!raw||!els) return [];
  const sums=new Array(els.length).fill(0); let cnt=0;
  for(let i=0;i<labels.length;i++){ if(labels[i]!==c) continue;
    const r=raw[i]; for(let j=0;j<els.length;j++) sums[j]+=r[j]; cnt++; }
  if(!cnt) return [];
  const total=sums.reduce((a,b)=>a+b,0);
  if(!(total>0)) return [];
  const ranked=els.map((e,j)=>[e, sums[j]/total*100])
    .filter(p=>p[1]>=S.ui.minPct)
    .sort((a,b)=>b[1]-a[1]);
  const keep=ranked.slice(0, S.ui.maxIso).map(p=>p[0]);
  if(ranked.length>S.ui.maxIso) keep.push('+'+(ranked.length-S.ui.maxIso)+'…');
  return keep;
}
const PICKER_EXTRA = ['#111827','#475569','#94A3B8','#E11D48','#F59E0B','#FACC15',
  '#84CC16','#10B981','#06B6D4','#3B82F6','#8B5CF6','#EC4899'];

 /**
 * Persist one cluster's colour to the shared config.
 *
 * The dialog redraws its own figures from there, so the scatters, strips and
 * heatmap follow the choice made here and it is saved with the project.
 *
 * @param {number} c Cluster id.
 * @param {?string} hex ``#RRGGBB``, or null to revert to the palette.
 */
function pushClusterColor(c, hex){
  if(!S.backend || typeof S.backend.set_cluster_color!=='function') return;
  try{ S.backend.set_cluster_color(c, hex||''); }
  catch(e){ }
}

let _cpop=null;
/** Close the cluster-colour popup and drop its global listeners. */
function closeColorPop(){
  if(!_cpop) return;
  _cpop.remove(); _cpop=null;
  window.removeEventListener('mousedown', _cpopOutside, true);
  window.removeEventListener('keydown', _cpopKey, true);
}
 /**
 * Close the colour popup when a click lands outside it.
 * @param {MouseEvent} e Capture-phase mousedown event.
 */
function _cpopOutside(e){ if(_cpop && !_cpop.contains(e.target)) closeColorPop(); }
 /**
 * Close the colour popup on Escape, without disturbing other handlers.
 * @param {KeyboardEvent} e Capture-phase keydown event.
 */
function _cpopKey(e){ if(e.key==='Escape'){ e.stopPropagation(); closeColorPop(); } }

 /**
 * Open a colour picker for cluster `c` and repaint once a colour is chosen.
 *
 * Implemented as an in-page popup rather than `<input type="color">`: Qt
 * WebEngine ships no colour-chooser dialog, so the native control silently
 * does nothing and the cluster never gets recoloured.
 *
 * @param {number} c Cluster id (noise, i.e. < 0, is not recolourable).
 * @param {number[]} labels Per-point cluster ids for the current frame.
 * @param {Element} [anchor] Element to position the popup against.
 */
function pickClusterColor(c, labels, anchor){
  if(c<0) return;
  closeColorPop();
  const pop=document.createElement('div'); pop.id='cpick';
  const apply=(hex)=>{
    if(hex==null) delete S.ui.colors[c]; else S.ui.colors[c]=hex;
    pushClusterColor(c, hex);
    if(labels && labels.length) buildLegend(labels); else refreshLegend();
    buildSwatches();
  };

  const cur=colorFor(c).toLowerCase();
  const seen=new Set(), grid=document.createElement('div'); grid.className='cpgrid';
  for(const hex of [...(S.palette||PALETTE), ...PICKER_EXTRA]){
    const key=String(hex).toLowerCase();
    if(seen.has(key)) continue; seen.add(key);
    const b=document.createElement('button');
    b.className='cpsw'+(key===cur?' on':'');
    b.style.background=hex; b.title=hex; b.type='button';
    b.onclick=()=>{ apply(hex); closeColorPop(); };
    grid.appendChild(b);
  }
  pop.appendChild(grid);

  const row=document.createElement('div'); row.className='cprow';
  const hexIn=document.createElement('input');
  hexIn.type='text'; hexIn.className='cphex'; hexIn.value=colorFor(c);
  hexIn.spellcheck=false; hexIn.maxLength=7; hexIn.setAttribute('aria-label','Hex colour');
  hexIn.oninput=()=>{
    const v=hexIn.value.trim();
    if(/^#[0-9a-fA-F]{6}$/.test(v)) apply(v);
  };
  hexIn.onkeydown=(e)=>{ if(e.key==='Enter') closeColorPop(); };
  const more=document.createElement('button');
  more.className='cpbtn'; more.type='button'; more.textContent='Custom…';
  more.title='Open the system colour picker';
  more.onclick=()=>{
    const start=colorFor(c);
    closeColorPop();
    if(S.backend && typeof S.backend.pick_color==='function'){
      try{ S.backend.pick_color(start, (hex)=>{ if(hex) apply(hex); }); return; }
      catch(e){ }
    }
    const inp=document.createElement('input');
    inp.type='color'; inp.value=start;
    inp.style.position='fixed'; inp.style.left='-9999px';
    document.body.appendChild(inp);
    inp.addEventListener('input', ()=>apply(inp.value));
    inp.addEventListener('change', ()=>{ apply(inp.value); inp.remove(); });
    inp.click();
  };
  const rst=document.createElement('button');
  rst.className='cpbtn'; rst.type='button'; rst.textContent='Default';
  rst.title='Use the palette colour for this cluster';
  rst.onclick=()=>{ apply(null); closeColorPop(); };
  row.appendChild(hexIn); row.appendChild(more); row.appendChild(rst);
  pop.appendChild(row);

  document.body.appendChild(pop);
  const r=(anchor && anchor.getBoundingClientRect) ? anchor.getBoundingClientRect() : null;
  const pw=pop.offsetWidth, ph=pop.offsetHeight;
  const vw=window.innerWidth, vh=window.innerHeight;
  let x=r ? r.left : (vw-pw)/2, y=r ? r.bottom+6 : (vh-ph)/2;
  x=Math.max(6, Math.min(x, vw-pw-6));
  if(y+ph>vh-6) y=r ? Math.max(6, r.top-ph-6) : Math.max(6, vh-ph-6);
  pop.style.left=x+'px'; pop.style.top=y+'px';

  _cpop=pop;
  setTimeout(()=>{
    if(!_cpop) return;
    window.addEventListener('mousedown', _cpopOutside, true);
    window.addEventListener('keydown', _cpopKey, true);
  },0);
  hexIn.focus(); hexIn.select();
}
/**
 * Legend rows kept alive across frames, keyed by cluster id.
 * @type {Map<number, Object>}
 */
let _legRows=new Map();
 /**
 * Refresh the cluster legend: colour swatch, dominant-element label and point
 * count per cluster.
 *
 * Rows are updated in place and only recreated when the set of cluster ids
 * changes. ``draw`` calls this on every animation frame, and replacing the
 * nodes each time would destroy the element between mousedown and mouseup, so
 * clicks would only register if both landed inside the same frame.
 *
 * Click an entry to *focus* that cluster — the view zooms to its particles and
 * every other cluster is dimmed rather than hidden, so the surrounding context
 * stays visible. Click it again (or press Escape) to zoom back out.
 * Alt-click still toggles a cluster's visibility outright.
 *
 * @param {number[]} labels Per-point cluster ids for the current frame.
 */
function buildLegend(labels){
  const counts=new Map(); for(const c of labels) counts.set(c,(counts.get(c)||0)+1);
  const keys=[...counts.keys()].sort((a,b)=>{
    if(a<0) return 1;
    if(b<0) return -1;
    return (counts.get(b)-counts.get(a)) || (a-b);
  });
  const box=$('legItems'); if(!box) return;

  if(_legRows.size!==keys.length || box.children.length!==keys.length
     || !keys.every(c=>_legRows.has(c))){
    box.innerHTML=''; _legRows=new Map();
    for(const c of keys) box.appendChild(makeLegendRow(c));
  }

  for(const c of keys){
    const row=_legRows.get(c); if(!row) continue;
    const cls='leg'+(S.hidden.has(c)?' off':'')
      +(S.focus===c?' on':'')+(isDimmed(c)?' dim':'');
    if(row.div.className!==cls) row.div.className=cls;
    const title=S.focus===c ? 'Click to zoom back out'
                            : 'Click to zoom to this cluster (⌥-click to hide it)';
    if(row.div.title!==title) row.div.title=title;
    const col=colorFor(c);
    if(row.col!==col){ row.sw.style.background=col; row.col=col; }
    if(row.labels!==labels || row.name==null){
      const top=c<0?[]:clusterTopElements(labels,c);
      const name=clusterTag(c)
        +(top.length?' · '+top.map(elementTokenHTML).join('·'):'');
      if(row.name!==name){ row.nm.innerHTML=name; row.name=name; }
      row.labels=labels;
    }
    const ct=String(counts.get(c));
    if(row.ct.textContent!==ct) row.ct.textContent=ct;
  }

  if(!S.playing){
    let out=false;
    for(let i=0;i<keys.length;i++){
      const row=_legRows.get(keys[i]);
      if(!row || box.children[i]!==row.div){ out=true; break; }
    }
    if(out){
      for(const c of keys){
        const row=_legRows.get(c);
        if(row) box.appendChild(row.div);
      }
    }
  }
}
 /**
 * Build one legend row and register it in :data:`_legRows`.
 *
 * The row's handlers are bound once and read the latest frame labels from the
 * row record, so :func:`buildLegend` never has to replace the node.
 *
 * @param {number} c Cluster id (negative for noise).
 * @returns {HTMLElement} The row element, not yet attached to the legend.
 */
function makeLegendRow(c){
  const div=document.createElement('div');
  const sw=document.createElement('span');
  sw.className='sw'; sw.title='Click to recolour';
  const nm=document.createElement('span');
  const ct=document.createElement('span'); ct.className='ct';
  div.appendChild(sw); div.appendChild(nm); div.appendChild(ct);
  const row={div, sw, nm, ct, labels:null, name:null, col:null};
  div.onclick=(e)=>{
    if(e.target===sw){ pickClusterColor(c, row.labels||[], sw); return; }
    if(e.altKey){
      if(S.hidden.has(c)) S.hidden.delete(c); else S.hidden.add(c);
      if(S.hidden.has(c) && S.focus===c){ S.focus=null; zoomToCluster(null); }
      refreshLegend(); return;
    }
    setFocus(c);
  };
  _legRows.set(c, row);
  return div;
}

/** Populate a select element with options and optionally set its value. */
function fillSelect(id, opts, val){
  const s=$(id); if(!s) return; s.innerHTML='';
  for(const o of opts){ const opt=document.createElement('option'); opt.value=o; opt.textContent=o; s.appendChild(opt); }
  if(val!=null) s.value=val;
}
/**
 * Descriptions shown under the Projection dropdown, one per method.
 * @type {Object<string,string>}
 */
const PROJ_HINTS = {
  'PCA': 'Linear, fast and reproducible; axes carry an explained-variance share.',
  't-SNE': 'Non-linear: preserves local neighbourhoods, so tight groups separate. Slower, and distances between groups mean little.',
  'UMAP': 'Non-linear: keeps local and some global structure, usually faster than t-SNE.',
  'None': 'No reduction — plot two raw element channels directly.',
};
/**
 * Fill the Projection dropdown with every method, including any whose optional
 * dependency is missing. Unavailable methods stay listed but disabled and
 * labelled with the reason, so the choice is visible rather than silently gone.
 * @param {Array<object|string>} opts Schema entries or bare names.
 * @param {string} val Method to preselect.
 */
function fillProjections(opts, val){
  const s=$('projSel'); if(!s) return;
  s.innerHTML='';
  const list=(opts||['PCA','t-SNE','UMAP','None']).map(
    o=>typeof o==='string' ? {name:o, available:true, reason:''} : o);
  S.projInfo={};
  for(const o of list){
    S.projInfo[o.name]=o;
    const opt=document.createElement('option');
    opt.value=o.name;
    opt.textContent=o.available ? o.name : o.name+' — unavailable';
    opt.disabled=!o.available;
    if(o.reason) opt.title=o.reason;
    s.appendChild(opt);
  }
  const pick=(val && S.projInfo[val] && S.projInfo[val].available) ? val : 'PCA';
  s.value=pick;
  S.proj=pick;
  updateProjHint();
}
/** Update the hint under the Projection dropdown for the current choice. */
function updateProjHint(){
  const el=$('projHint'), s=$('projSel'); if(!el||!s) return;
  const info=(S.projInfo||{})[s.value];
  el.textContent=(info && !info.available)
    ? info.reason+' — PCA is used instead.'
    : (PROJ_HINTS[s.value]||'');
}
/** Populate the algorithm, data and projection controls from the schema. */
function buildPanel(){
  const algos=Object.keys(S.schema.algorithms), sel=$('algoSel'); sel.innerHTML='';
  for(const a of algos){ const o=document.createElement('option'); o.value=a; o.textContent=a; sel.appendChild(o); }
  sel.value=S.algo;
  sel.onchange=()=>{ S.algo=sel.value;
    if(S.backend && S.backend.set_config) S.backend.set_config(JSON.stringify({algorithm:S.algo}));
    buildAlgoParams(); scheduleRun(); };
  fillSelect('scalingSel', S.schema.scalings||['CLR','ILR','Robust Z-score','None']);
  fillSelect('dataTypeSel', S.schema.data_types||['Counts']);
  fillProjections(S.schema.projections, S.proj);
  buildAlgoParams();
}
/** Reflect the shared node config in the Data, View and Algorithm controls. */
function reflectConfig(state){
  const c=state.config||{};
  if($('scalingSel') && c.scaling) $('scalingSel').value=c.scaling;
  if($('dataTypeSel') && c.data_type) $('dataTypeSel').value=c.data_type;
  if($('filterZeros') && c.filter_zeros!=null) $('filterZeros').checked=!!c.filter_zeros;
  if($('minType') && c.min_particle_type_count!=null){ $('minType').value=c.min_particle_type_count;
    $('vMinType').textContent=c.min_particle_type_count;
    $('minType').style.setProperty('--pct',((c.min_particle_type_count-1)/(100-1)*100)+'%'); }
  if($('algoSel') && state.algorithm) $('algoSel').value=state.algorithm;
  if($('projSel') && state.projection){
    const info=(S.projInfo||{})[state.projection];
    if(!info || info.available) $('projSel').value=state.projection;
    updateProjHint();
  }
  if($('viewSel') && state.dims) $('viewSel').value=String(state.dims);
  if($('view3dHint')) $('view3dHint').style.display=(state.dims===3)?'block':'none';
  if(c.label_mode){
    S.ui.labelMode=c.label_mode;
    const lm=$('labelMode'); if(lm) lm.value=c.label_mode;
  }
  if(c.display_max_isotopes!=null) S.ui.maxIso=Math.max(1,+c.display_max_isotopes);
  if(c.display_min_pct!=null) S.ui.minPct=Math.max(0,+c.display_min_pct);
}
/** Send a preprocessing config change to the backend. */
function pushConfig(patch){
  if(S.backend && S.backend.set_config){
    $('note').textContent='Updating projection…';
    S.backend.set_config(JSON.stringify(patch));
  }
}
/** Persist one algorithm parameter to the shared node config. */
function pushParam(key, value){
  if(S.backend && S.backend.set_param)
    S.backend.set_param(S.algo, key, JSON.stringify(value));
}
/** Build the parameter widgets for the selected algorithm from shared values. */
function buildAlgoParams(){
  const spec=S.schema.algorithms[S.algo];
  $('blurb').innerHTML=`<span class="tag">LIVE STEPS</span><br>${spec.blurb}`;
  const box=$('algoParams'); box.innerHTML=''; S.params={};
  const vals=(S.paramValues&&S.paramValues[S.algo])||{};
  S.paramEls={};
  for(const p of spec.params){ const v=(p.key in vals)?vals[p.key]:p.default;
    S.params[p.key]=v;
    const w=(p.type==='choice')?choiceField(p,v)
           :(p.type==='bool')?boolField(p,v):rangeField(p,v);
    S.paramEls[p.key]=w;
    box.appendChild(w); }
  syncParamAvailability();
}
/**
 * Grey out any parameter this illustration cannot honour.
 *
 * Two cases: a parameter the simplified stepper never reads (`applies:false`),
 * and one whose relevance depends on another (`only_if`), such as the distance
 * metric under Ward linkage. Both stay visible with a reason rather than
 * sitting there looking active while changing nothing.
 */
function syncParamAvailability(){
  const spec=S.schema && S.schema.algorithms[S.algo];
  if(!spec || !S.paramEls) return;
  for(const p of spec.params){
    const wrap=S.paramEls[p.key];
    if(!wrap) continue;
    let off=(p.applies===false), why=p.applies===false ? 'not used by this illustration' : '';
    if(!off && p.only_if){
      const other=S.params[p.only_if.key];
      const blocked=(p.only_if.not||[]).some(v=>String(v)===String(other));
      if(blocked){ off=true; why=`not applicable with ${p.only_if.key} = ${other}`; }
    }
    wrap.classList.toggle('inert', off);
    for(const el of wrap.querySelectorAll('input,select')) el.disabled=off;
    const badge=wrap.querySelector('.inertTag');
    if(off && !badge){
      const t=document.createElement('div');
      t.className='hint inertTag'; t.textContent=why;
      wrap.appendChild(t);
    } else if(off && badge){ badge.textContent=why; }
    else if(badge){ badge.remove(); }
  }
}
/** Create a labelled on/off toggle for a boolean parameter. */
function boolField(p,val){
  const wrap=document.createElement('div'); wrap.className='field';
  const lab=document.createElement('label'); lab.className='toggle';
  const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=!!val;
  const tr=document.createElement('span'); tr.className='track';
  lab.appendChild(cb); lab.appendChild(tr); lab.appendChild(document.createTextNode(' '+p.label));
  cb.onchange=()=>{ S.params[p.key]=cb.checked; pushParam(p.key,cb.checked);
    syncParamAvailability(); scheduleRun(); };
  wrap.appendChild(lab); return wrap;
}
/** Create a labelled slider control for a numeric parameter. */
function rangeField(p,val){
  const wrap=document.createElement('div'); wrap.className='field'; const isInt=p.type==='int';
  const cur=(val!=null)?val:p.default;
  wrap.innerHTML=`<label>${p.label}<span class="val" id="v_${p.key}">${cur}</span></label>`;
  const r=document.createElement('input'); r.type='range'; r.min=p.min; r.max=p.max;
  r.step=p.step||(isInt?1:0.01); r.value=cur;
  const setPct=()=>r.style.setProperty('--pct',((r.value-p.min)/((p.max-p.min)||1)*100)+'%'); setPct();
  r.oninput=()=>{ const v=isInt?parseInt(r.value):parseFloat(r.value); S.params[p.key]=v;
    $('v_'+p.key).textContent=isInt?v:v.toFixed(2); setPct(); pushParam(p.key,v);
    syncParamAvailability(); scheduleRun(); };
  wrap.appendChild(r);
  if(p.help){ const hl=document.createElement('div'); hl.className='hint'; hl.textContent=p.help; wrap.appendChild(hl); }
  return wrap;
}
/** Create a labelled dropdown control for a categorical parameter. */
function choiceField(p,val){
  const wrap=document.createElement('div'); wrap.className='field';
  wrap.innerHTML=`<label>${p.label}</label>`; const s=document.createElement('select');
  for(const o of p.options){ const opt=document.createElement('option'); opt.value=o; opt.textContent=o; s.appendChild(opt); }
  s.value=(val!=null)?val:p.default;
  s.onchange=()=>{ S.params[p.key]=s.value; pushParam(p.key,s.value);
    syncParamAvailability(); scheduleRun(); };
  wrap.appendChild(s); return wrap;
}

/** No-op kept for compatibility (the play button was removed). */
function syncPlayBtn(){ const b=$('playBtn'); if(b) b.textContent=S.playing?'❚❚':'▶'; }
/** Wire up all panel, projection and canvas interactions. */
function bindControls(){
  window.addEventListener('keydown',(e)=>{
    if(e.key==='Escape' && !_cpop && S.focus!=null){ setFocus(null); }
  });
  $('menuBtn').onclick=()=>$('panel').classList.toggle('open');
  const pc=$('panelClose'); if(pc) pc.onclick=()=>$('panel').classList.remove('open');
  // Cluster button: run (animated) and leave the panel exactly as it is.
  $('runBtn').onclick=()=>run(true);
  const speed=$('speed');
  speed.oninput=()=>{ S.fps=+speed.value; $('vSpeed').textContent=speed.value+'×';
    speed.style.setProperty('--pct',((speed.value-1)/(30-1)*100)+'%'); };
  speed.style.setProperty('--pct',((S.fps-1)/(30-1)*100)+'%');

  const projSel=$('projSel'), viewSel=$('viewSel');
  function changeProjection(){
    S.proj=projSel.value; const d=+viewSel.value;
    updateProjHint();
    $('view3dHint').style.display = d===3?'block':'none';
    if(S.backend && S.backend.set_projection){
      $('note').textContent=`Computing ${S.proj} ${d}D projection…`;
      S.backend.set_projection(S.proj, d);
    }
  }
  if(projSel) projSel.onchange=changeProjection;
  if(viewSel) viewSel.onchange=changeProjection;

  const scalingSel=$('scalingSel'), dataTypeSel=$('dataTypeSel'), filterZeros=$('filterZeros');
  if(scalingSel) scalingSel.onchange=()=>pushConfig({scaling:scalingSel.value});
  if(dataTypeSel) dataTypeSel.onchange=()=>pushConfig({data_type:dataTypeSel.value});
  if(filterZeros) filterZeros.onchange=()=>pushConfig({filter_zeros:filterZeros.checked});
  const minType=$('minType');
  if(minType){ minType.oninput=()=>{ $('vMinType').textContent=minType.value;
    minType.style.setProperty('--pct',((minType.value-1)/(100-1)*100)+'%');
    clearTimeout(minType._t); minType._t=setTimeout(()=>pushConfig({min_particle_type_count:+minType.value}),250); }; }

  bindBoxes();
  bindMenu();
  bindSettings();

  canvas.addEventListener('mousedown',(e)=>{ if(curDims()===3){
    S.tween=null;
    S.drag3d={x:e.clientX,y:e.clientY,az:S.rot.az,el:S.rot.el}; } });
  window.addEventListener('mouseup',()=>{ S.drag3d=null; });
  canvas.addEventListener('mousemove',(e)=>{ if(!S.drag3d) return;
    S.rot.az=S.drag3d.az+(e.clientX-S.drag3d.x)*0.01;
    S.rot.el=Math.max(-1.45,Math.min(1.45,S.drag3d.el+(e.clientY-S.drag3d.y)*0.01)); });
  canvas.addEventListener('wheel',(e)=>{ if(curDims()!==3) return; e.preventDefault();
    S.tween=null;
    S.v3.zoom=Math.max(0.3,Math.min(FOCUS_MAX_ZOOM,(S.v3.zoom||1)*(e.deltaY<0?1.1:0.9)));
    S.v3.scale=(S.v3.baseScale||1)*S.v3.zoom; },{passive:false});

  canvas.addEventListener('mousemove',onHover);
  canvas.addEventListener('mouseleave',()=>{ S.hoverIdx=-1; $('tip').style.display='none'; });
  window.addEventListener('resize',()=>{ resize(); if(S.data && !S.data.empty) fitView(); });
}
/** Pin a floating box to explicit left/top so it can be dragged and resized. */
function unpinBox(box){
  const r=box.getBoundingClientRect();
  box.style.left=r.left+'px'; box.style.top=r.top+'px';
  box.style.right='auto'; box.style.bottom='auto';
  return r;
}
/** Clear every inline geometry override, returning a box to its CSS default. */
function resetBox(boxId, bodyId){
  const box=$(boxId), body=$(bodyId);
  if(box) for(const p of ['left','top','right','bottom','width','height'])
    box.style.removeProperty(p);
  if(body) body.style.removeProperty('height');
}
/**
 * Make a floating box movable by its header, resizable by its corner grip and
 * collapsible by its caret. Width comes from the box, height from its body —
 * the body must not be a flex item, or the explicit height is ignored and the
 * box would only ever grow sideways.
 * @param {object} ids Element ids: box, head, body, grip, toggle.
 * @param {string} flag Key in S holding the collapsed state.
 */
function bindFloatBox(ids, flag){
  const box=$(ids.box), head=$(ids.head), body=$(ids.body),
        grip=$(ids.grip), tgl=$(ids.toggle);
  if(!box) return;
  let drag=null, size=null;
  if(tgl) tgl.onclick=(e)=>{ e.stopPropagation(); S[flag]=!S[flag];
    tgl.textContent=S[flag]?'▴':'▾';
    tgl.title=S[flag]?'Expand':'Collapse'; };
  if(head) head.addEventListener('mousedown',(e)=>{
    if(e.target===tgl) return;
    const r=unpinBox(box);
    drag={dx:e.clientX-r.left, dy:e.clientY-r.top, w:r.width};
    e.preventDefault();
  });
  if(grip) grip.addEventListener('mousedown',(e)=>{
    const r=unpinBox(box);
    box.style.width=r.width+'px';
    size={x:e.clientX, y:e.clientY, w:r.width,
          h:body?body.getBoundingClientRect().height:180};
    e.preventDefault(); e.stopPropagation();
  });
  window.addEventListener('mousemove',(e)=>{
    if(drag){
      box.style.left=Math.max(4, Math.min(window.innerWidth-drag.w-4, e.clientX-drag.dx))+'px';
      box.style.top =Math.max(4, Math.min(window.innerHeight-40, e.clientY-drag.dy))+'px';
    } else if(size && body){
      box.style.width =Math.max(210, Math.min(window.innerWidth-20,  size.w+(e.clientX-size.x)))+'px';
      body.style.height=Math.max(50,  Math.min(window.innerHeight-110, size.h+(e.clientY-size.y)))+'px';
    }
  });
  window.addEventListener('mouseup',()=>{ drag=null; size=null; });
}
/** Wire both floating boxes and the chips that bring them back. */
function bindBoxes(){
  bindFloatBox({box:'inset', head:'insetHead', body:'insetBody',
                grip:'insetGrip', toggle:'insetToggle'}, 'insetCollapsed');
  bindFloatBox({box:'eqbox', head:'eqHead', body:'eqBody',
                grip:'eqGrip', toggle:'eqToggle'}, 'eqCollapsed');
  const is=$('insetShow'), es=$('eqShow');
  if(is) is.onclick=()=>{ S.insetOn=true; syncSettings(); };
  if(es) es.onclick=()=>{ S.eqOn=true; syncSettings(); };
}

/** Show the context menu at the pointer, clamped to the window. */
function openMenu(x,y){
  const m=$('ctxmenu'); if(!m) return;
  m.classList.add('show');
  const r=m.getBoundingClientRect();
  m.style.left=Math.min(x, window.innerWidth-r.width-6)+'px';
  m.style.top =Math.min(y, window.innerHeight-r.height-6)+'px';
}
/** Hide the context menu. */
function closeMenu(){ const m=$('ctxmenu'); if(m) m.classList.remove('show'); }
/** Wire the right-click menu on the plot and both floating boxes. */
function bindMenu(){
  const m=$('ctxmenu'); if(!m) return;
  const onCtx=(e)=>{ e.preventDefault(); openMenu(e.clientX, e.clientY); };
  for(const id of ['stage','inset','eqbox']){
    const el=$(id); if(el) el.addEventListener('contextmenu', onCtx);
  }
  window.addEventListener('click', closeMenu);
  window.addEventListener('scroll', closeMenu, true);
  m.addEventListener('click',(e)=>{
    const b=e.target.closest ? e.target.closest('button') : null;
    if(!b) return;
    const act=b.getAttribute('data-act');
    if(act==='settings') openSettings();
    else if(act==='export') openSettings('tExport');
    else if(act==='detail'){ S.insetOn=!S.insetOn; syncSettings(); }
    else if(act==='equation'){ S.eqOn=!S.eqOn; syncSettings(); }
    else if(act==='fit'){ S.v3.zoom=1; S.focus=null; fitView(); refreshLegend(); }
    else if(act==='boxes'){ resetBox('inset','insetBody'); resetBox('eqbox','eqBody'); }
    else if(act==='colors') resetColors();
    closeMenu();
  });
}

/** Repaint the legend from the frame currently on screen. */
function refreshLegend(){
  const fr=S.frames.length?frameAt(Math.floor(S.t)):null;
  if(fr && fr.labels) buildLegend(fr.labels);
}
/** Drop every per-cluster colour override. */
function resetColors(){
  closeColorPop(); S.ui.colors={};
  if(S.backend && typeof S.backend.reset_cluster_colors==='function'){
    try{ S.backend.reset_cluster_colors(); }catch(e){ }
  }
  refreshLegend(); buildSwatches();
}
/** Rebuild the colour swatch row in the settings dialog. */
function buildSwatches(){
  const box=$('swatches'); if(!box) return;
  const fr=S.frames.length?frameAt(Math.floor(S.t)):null;
  const ids=new Set();
  if(fr && fr.labels) for(const c of fr.labels) if(c>=0) ids.add(c);
  box.innerHTML='';
  for(const c of [...ids].sort((a,b)=>a-b)){
    const d=document.createElement('div');
    d.className='sw2'; d.style.background=colorFor(c); d.title=clusterTag(c);
    d.onclick=()=>{ pickClusterColor(c, fr?fr.labels:[], d); };
    box.appendChild(d);
  }
}
/** Fill the Info tab with the dataset and view details. */
function buildInfo(){
  const box=$('infoTable'), d=S.data||{};
  if(!box) return;
  const fr=S.frames.length?frameAt(Math.floor(S.t)):null;
  const m=(fr&&fr.metrics)||{};
  const vr=(d.var_ratio||[]).map(v=>(v*100).toFixed(1)+'%').join(' / ');
  const rows=[
    ['Algorithm', S.algo],
    ['Particles shown', (d.n!=null?d.n:'–')+(d.n_total&&d.n_total>d.n?` of ${d.n_total}`:'')],
    ['Elements', (d.elements||[]).length],
    ['Projection', `${d.projection||'PCA'} · ${d.dims||2}D`],
    ['Explained variance', vr||'—'],
    ['Data type', (d.config&&d.config.data_type)||'—'],
    ['Scaling', (d.config&&d.config.scaling)||'—'],
    ['Clusters (this step)', m.n_clusters!=null?m.n_clusters:'–'],
    ['Noise points', m.n_noise!=null?m.n_noise:'–'],
    ['Inertia', m.inertia!=null?(+m.inertia).toFixed(2):'–'],
    ['Frames buffered', S.frames.length],
    ['Step', fr?(fr.note||''):'—'],
  ];
  box.innerHTML=rows.map(([k,v])=>
    `<div class="irow"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
}
/** Push the current state into every settings control. */
function syncSettings(){
  const set=(id,v)=>{ const el=$(id); if(el) el.checked=v; };
  set('insetOn', S.insetOn); set('eqOn', S.eqOn); set('legendOn', S.legendOn);
  const lg=$('legend'); if(lg) lg.style.display=S.legendOn?'':'none';
}
/** Open the settings dialog, optionally on a given tab. */
function openSettings(tab){
  const m=$('modal'); if(!m) return;
  syncSettings(); buildSwatches(); buildInfo();
  if(tab) selectTab(tab);
  m.classList.add('show');
}
/** Switch the settings dialog to one tab. */
function selectTab(id){
  for(const b of document.querySelectorAll('.stab'))
    b.classList.toggle('on', b.getAttribute('data-tab')===id);
  for(const p of document.querySelectorAll('.spane'))
    p.classList.toggle('on', p.id===id);
}
/** Wire the settings dialog: tabs, appearance, boxes, export. */
function bindSettings(){
  const root=document.documentElement.style, m=$('modal');
  const pct=(el,mn,mx)=>el.style.setProperty('--pct',
    ((el.value-mn)/((mx-mn)||1)*100)+'%');
  const close=$('setClose'); if(close) close.onclick=()=>m.classList.remove('show');
  if(m) m.addEventListener('click',(e)=>{ if(e.target===m) m.classList.remove('show'); });
  window.addEventListener('keydown',(e)=>{ if(e.key==='Escape'){
    if(m) m.classList.remove('show'); closeMenu(); } });
  for(const b of document.querySelectorAll('.stab'))
    b.onclick=()=>selectTab(b.getAttribute('data-tab'));

  const fontSel=$('fontSel'), fstyle=$('fontStyleSel'), fs=$('fontSize'),
        lm=$('labelMode'), ps=$('pointSize'), cs=$('centSize'), cr=$('colorReset');
  if(fontSel) fontSel.onchange=()=>{ S.ui.font=fontSel.value;
    root.setProperty('--ui-font', uiFontStack()); };
  if(fstyle) fstyle.onchange=()=>{ S.ui.fontStyle=fstyle.value;
    root.setProperty('--ui-weight', fstyle.value.includes('bold')?'650':'400');
    root.setProperty('--ui-italic', fstyle.value.includes('italic')?'italic':'normal');
    document.body.style.fontWeight=fstyle.value.includes('bold')?'650':'';
    document.body.style.fontStyle=fstyle.value.includes('italic')?'italic':''; };
  if(fs){ fs.oninput=()=>{ S.ui.fontSize=parseFloat(fs.value);
    $('vFontSize').textContent=fs.value;
    root.setProperty('--ui-size', S.ui.fontSize+'px'); pct(fs,8,40); };
    pct(fs,8,40); }
  if(lm) lm.onchange=()=>{
    S.ui.labelMode=lm.value;
    if(S.backend && typeof S.backend.set_label_mode==='function'){
      try{ S.backend.set_label_mode(lm.value); }catch(e){ }
    }
    refreshLegend();
  };
  if(ps){ ps.oninput=()=>{ S.ui.pointSize=parseFloat(ps.value);
    $('vPointSize').textContent=S.ui.pointSize>0?ps.value:'auto'; pct(ps,0,14); };
    pct(ps,0,14); }
  if(cs){ cs.oninput=()=>{ S.ui.centSize=parseFloat(cs.value);
    $('vCentSize').textContent=cs.value; pct(cs,3,28); };
    pct(cs,3,28); }
  if(cr) cr.onclick=resetColors;

  const io=$('insetOn'), eo=$('eqOn'), lo=$('legendOn'), br=$('boxReset');
  if(io) io.onchange=()=>{ S.insetOn=io.checked; };
  if(eo) eo.onchange=()=>{ S.eqOn=eo.checked; };
  if(lo) lo.onchange=()=>{ S.legendOn=lo.checked;
    const lg=$('legend'); if(lg) lg.style.display=S.legendOn?'':'none'; };
  if(br) br.onclick=()=>{ resetBox('inset','insetBody'); resetBox('eqbox','eqBody'); };

  const sc=$('expScale'), ef=$('expFont'), tr=$('expTransparent');
  if(sc) sc.onchange=()=>{ S.exp.scale=+sc.value; };
  if(ef){ ef.oninput=()=>{ S.exp.fontBoost=parseFloat(ef.value);
    $('vExpFont').textContent=parseFloat(ef.value).toFixed(2)+'×'; pct(ef,1,2.5); };
    pct(ef,1,2.5); }
  if(tr) tr.onchange=()=>{ S.exp.transparent=tr.checked; };
  const ep=$('expPlot'), ei=$('expInset');
  if(ep) ep.onclick=()=>exportPlotPNG();
  if(ei) ei.onclick=()=>exportInsetPNG();
}

/** Trigger a browser download of a canvas as PNG. */
function downloadCanvas(cv, name){
  try{
    const a=document.createElement('a');
    a.href=cv.toDataURL('image/png'); a.download=name;
    document.body.appendChild(a); a.click(); a.remove();
    showStatus('Choose where to save '+name+'…');
  }catch(e){ showStatus('Export failed: '+e.message); }
}
/** Filename stem for an export, e.g. "cluster-lab_K-Means_3x". */
function exportName(what){
  const algo=String(S.algo||'plot').replace(/[^\w+-]+/g,'-');
  return `cluster-lab_${what}_${algo}_${S.exp.scale}x.png`;
}
/** Prepare an offscreen canvas at the export scale, background filled. */
function makeExportCanvas(w,h){
  const s=S.exp.scale;
  const cv=document.createElement('canvas');
  cv.width=Math.round(w*s); cv.height=Math.round(h*s);
  const c=cv.getContext('2d');
  c.setTransform(s,0,0,s,0,0);
  if(!S.exp.transparent){ c.fillStyle=THEME.bg; c.fillRect(0,0,w,h); }
  return {cv, c};
}
/** Export the main scatter at the chosen scale, with enlarged type. */
function exportPlotPNG(){
  if(!S.data || S.data.empty){ showStatus('Nothing to export yet'); return; }
  const w=canvas.clientWidth, h=canvas.clientHeight;
  const {cv,c}=makeExportCanvas(w,h);
  const saved=ctx;
  ctx=c; EXPORT={scale:S.exp.scale};
  try{ draw(); } finally { ctx=saved; EXPORT=null; }
  downloadCanvas(cv, exportName('plot'));
}
/** Export the detail view, drawing its title and subtitle into the image. */
function exportInsetPNG(){
  const A=S.frames.length?frameAt(Math.floor(S.t)):null;
  const d=A && A.extra && A.extra.inset;
  if(!d){ showStatus('No detail view to export'); return; }
  const w=Math.max(320, icanvas.clientWidth), hb=Math.max(180, icanvas.clientHeight);
  const head=Math.max(34, S.ui.fontSize*S.exp.fontBoost*2.4), h=hb+head;
  const {cv,c}=makeExportCanvas(w,h);
  const saved=ictx;
  ictx=c; EXPORT={scale:S.exp.scale};
  try{
    c.fillStyle=THEME.text; c.textAlign='left'; c.textBaseline='top';
    c.font=uiFont(0.95,'bold'); c.fillText(d.title||'Detail', 10, 6);
    c.globalAlpha=.65; c.font=uiFont(0.74);
    c.fillText(d.subtitle||'', 10, 6+uiSize()*1.15); c.globalAlpha=1;
    c.save(); c.translate(0, head);
    c.font=uiFont(0.72);
    if(d.kind==='curve') insetCurve(d,w,hb);
    else if(d.kind==='bars') insetBars(d,w,hb);
    else if(d.kind==='dendrogram') insetDendro(d,w,hb);
    else if(d.kind==='grid') insetGrid(d,w,hb);
    c.restore();
  } finally { ictx=saved; EXPORT=null; }
  downloadCanvas(cv, exportName('detail'));
}

/** Show a tooltip for the particle nearest the cursor. */
function onHover(e){
  if(!S.data||S.data.empty||S.drag3d){ return; }
  const rect=canvas.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  const fr=S.frames.length?frameAt(Math.round(S.t)):null;
  const pos=(fr&&fr.positions)?fr.positions:S.data.xy;
  let best=-1,bd=144;
  for(let i=0;i<pos.length;i++){ const s=screen(pos[i]),dx=s[0]-mx,dy=s[1]-my,d=dx*dx+dy*dy; if(d<bd){bd=d;best=i;} }
  S.hoverIdx=best; const tip=$('tip');
  if(best<0){ tip.style.display='none'; return; }
  const raw=S.data.raw[best],els=S.data.elements;
  const pairs=els.map((e,j)=>[e,raw[j]]).filter(p=>p[1]>0).sort((a,b)=>b[1]-a[1]).slice(0,5);
  const cl=fr?fr.labels[best]:-1;
  tip.innerHTML=`<div class="th">${clusterTag(cl)} `+
    `<span style="color:${colorFor(cl)}">●</span></div>`+
    pairs.map(p=>`<div class="row"><span>${elementLabelHTML(p[0])}</span>`+
      `<b>${esc(p[1])}</b></div>`).join('');
  tip.style.display='block';
  tip.style.left=Math.min(window.innerWidth-220,e.clientX+14)+'px';
  tip.style.top=(e.clientY+14)+'px';
}
/** Briefly show a status message. */
function showStatus(t){ const el=$('status'); el.textContent=t; el.classList.add('show');
  clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),1400); }
/** Resize the canvas backing store to the device pixel ratio. */
function resize(){ DPR=window.devicePixelRatio||1;
  canvas.width=canvas.clientWidth*DPR; canvas.height=canvas.clientHeight*DPR; ctx.setTransform(DPR,0,0,DPR,0,0); }

/** Return a minimal in-browser backend for previewing without Qt. */
function makeMockBackend(){
  const sig=()=>{ const cbs=[]; return {connect:f=>cbs.push(f),emit:(...a)=>cbs.forEach(f=>f(...a))}; };
  const b={stateReady:sig(),frameReady:sig(),runFinished:sig(),status:sig()};
  const N=500,blobs=[[-.6,-.4],[.6,-.3],[0,.6],[.7,.6]],xy=[],raw=[],els=['Fe','Ti','Si','Ce'];
  for(let i=0;i<N;i++){ const k=i%4,[cx,cy]=blobs[k]; xy.push([cx+(Math.random()-.5)*.4,cy+(Math.random()-.5)*.4]);
    const r=[0,0,0,0]; r[k]=+(Math.random()*80+20).toFixed(1); raw.push(r); }
  b.get_theme=(cb)=>cb(JSON.stringify({bg:'#1e1e1e',text:'#d4d4d4',accent:'#007acc',muted2:'#9d9d9d',dark:true}));
  b.get_schema=(cb)=>cb(JSON.stringify({algorithms:{'K-Means':{blurb:'Preview mock (Qt not detected).',
    true_iteration:true,params:[{key:'k',label:'Clusters (k)',type:'int',default:4,min:2,max:8,step:1,help:''}]}},
    scalings:['CLR','ILR','Robust Z-score','None'],data_types:['Counts'],
    projections:[{name:'PCA',available:true,reason:''},
      {name:'t-SNE',available:true,reason:''},
      {name:'UMAP',available:false,reason:'umap not installed (ImportError)'},
      {name:'None',available:true,reason:''}]}));
  b.get_state=(cb)=>cb(JSON.stringify({n:N,n_total:N,empty:false,elements:els,xy,samples:xy.map(()=>'Sample'),
    sample_names:['Sample'],raw,var_ratio:[.6,.25],dims:2,projection:'PCA',palette:PALETTE,seq:1,
    algorithm:'K-Means',param_values:{'K-Means':{k:4}},
    config:{scaling:'CLR',data_type:'Counts',filter_zeros:true,algorithm:'K-Means'},
    theme:{bg:'#1e1e1e',text:'#d4d4d4',accent:'#007acc',muted2:'#9d9d9d'}}));
  b.set_projection=(_p,_d)=>{};
  b.set_config=(_j)=>{};
  b.set_param=(_a,_k,_v)=>{};
  b.stop=()=>{};
  b.run_sklearn=()=>{
    const labels=xy.map(p=>{ let best=0,bd=1e9;
      for(let k=0;k<blobs.length;k++){ const d=Math.hypot(p[0]-blobs[k][0],p[1]-blobs[k][1]);
        if(d<bd){bd=d;best=k;} } return best; });
    setTimeout(()=>receiveCompare({error:null,note:'preview mock',labels,
      centroids:blobs.map(b2=>b2.slice()),metrics:{n_clusters:blobs.length,n_noise:0}}),400);
  };
  b.run=(algo,pj)=>{ const k=JSON.parse(pj).k||4; let C=blobs.slice(0,k).map(c=>[c[0]+.3,c[1]+.3]),step=0;
    const iv=setInterval(()=>{ const labels=xy.map(p=>{let bi=0,bd=1e9;C.forEach((c,j)=>{const d=(c[0]-p[0])**2+(c[1]-p[1])**2;if(d<bd){bd=d;bi=j;}});return bi;});
      for(let j=0;j<k;j++){const pts=xy.filter((_,i)=>labels[i]===j); if(pts.length)C[j]=[pts.reduce((s,p)=>s+p[0],0)/pts.length,pts.reduce((s,p)=>s+p[1],0)/pts.length];}
      b.frameReady.emit(JSON.stringify({iter:step,note:'Mock iteration '+(step+1),labels,centroids:C.map(c=>[...c]),
        positions:null,extra:{},converged:step>6,metrics:{n_clusters:k,n_noise:0,inertia:100-step*8}}));
      if(++step>7){clearInterval(iv);b.runFinished.emit('{}');} },260); };
  return b;
}

window.addEventListener('load',()=>{ resize(); bindControls(); syncPlayBtn(); requestAnimationFrame(tick); boot(); });
