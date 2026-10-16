/** Browser rendering only. Analytics and predictive calculations live in backend/app/services. */
const NS = 'http://www.w3.org/2000/svg';
const moneyShort = (v, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(v);
const shortNum = v => Math.abs(v) >= 1e9 ? `${(v/1e9).toFixed(1)}B` : Math.abs(v) >= 1e6 ? `${(v/1e6).toFixed(1)}M` : Math.abs(v) >= 1e3 ? `${(v/1e3).toFixed(1)}K` : Number(v).toFixed(2);
const formatDay = date => new Date(`${date}T12:00:00`).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
const clamp = (v,lo,hi) => Math.min(hi,Math.max(lo,v));
const svgEl = (tag, attributes = {}) => { const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attributes)) el.setAttribute(k,String(v));return el; };
const line = (series, xAt, yAt) => series.map((v,i) => v == null || !Number.isFinite(v) ? null : `${i?'L':'M'}${xAt(i).toFixed(2)},${yAt(v).toFixed(2)}`).filter(Boolean).join(' ');

function chartFrame(container, min, max, dates, opts={}) {
  container.replaceChildren();
  const width = Math.max(340, container.clientWidth || 880), height = container.clientHeight || 310;
  const box = {left:9, right:65, top:22, bottom:43};
  const graphW = width - box.left - box.right, graphH = height - box.top - box.bottom;
  const spread = Math.max(max-min, Math.abs(max)*0.015, .01);
  const floor = min-spread*.12, ceil=max+spread*.12;
  const x = i => box.left + (dates.length>1 ? i/(dates.length-1) : .5)*graphW;
  const y = v => box.top + (ceil-v)/(ceil-floor)*graphH;
  const svg = svgEl('svg',{viewBox:`0 0 ${width} ${height}`, role:'presentation'});
  const defs=svgEl('defs');
  const grad=svgEl('linearGradient',{id:opts.gradient||'historyFill', x1:'0%', y1:'0%', x2:'0%',y2:'100%'});
  grad.append(svgEl('stop',{offset:'0%','stop-color':opts.color||'#29ddcb','stop-opacity':'.20'}),svgEl('stop',{offset:'100%','stop-color':opts.color||'#29ddcb','stop-opacity':'0'}));defs.append(grad);svg.append(defs);
  for(let i=0;i<5;i++){
    const value=floor+(ceil-floor)*(4-i)/4;
    const yy=y(value);
    svg.append(svgEl('line',{x1:box.left,y1:yy,x2:width-box.right+5,y2:yy,class:'chart-grid'}));
    const tick=svgEl('text',{x:width-4,y:yy+4,'text-anchor':'end',class:'chart-axis'});
    tick.textContent=shortNum(value);svg.append(tick);
  }
  for(let i=0;i<6;i++){
    const at=Math.round(i*(dates.length-1)/5);
    const tick=svgEl('text',{x:x(at),y:height-13,'text-anchor':i===0?'start':i===5?'end':'middle',class:'chart-axis'});
    tick.textContent=new Date(`${dates[at]}T12:00:00`).toLocaleDateString('en-US',{month:'short',year:'2-digit'});
    svg.append(tick);
  }
  container.append(svg);
  return {svg,width,height,box,graphW,graphH,floor,ceil,x,y};
}

function installTooltip(container, frame, rows, currency, printer) {
  const {svg,x,box,graphW} = frame;
  const rule=svgEl('line',{x1:0,x2:0,y1:box.top,y2:frame.height-box.bottom,class:'chart-hover-line',visibility:'hidden'});
  const dot=svgEl('circle',{r:5,fill:'#29ddcb',stroke:'#15283c','stroke-width':3,visibility:'hidden'});
  svg.append(rule,dot);
  const tip=document.createElement('div');tip.className='chart-tooltip';tip.style.display='none';container.append(tip);
  svg.addEventListener('mousemove',event=>{
    const rect=svg.getBoundingClientRect();
    const localX=(event.clientX-rect.left)*frame.width/rect.width;
    const i=clamp(Math.round((localX-box.left)/graphW*(rows.length-1)),0,rows.length-1);
    const r=rows[i], px=x(i), value=printer.value(r);
    if(!Number.isFinite(value)) return;
    rule.setAttribute('x1',px);rule.setAttribute('x2',px);rule.setAttribute('visibility','visible');
    dot.setAttribute('cx',px);dot.setAttribute('cy',frame.y(value));dot.setAttribute('visibility','visible');
    tip.textContent=`${formatDay(r.date)}\n${printer.label(r)}: ${moneyShort(value,currency)}${printer.extra(r)}`;
    tip.style.whiteSpace='pre-line';tip.style.display='block';
    const tipX=clamp((px/frame.width)*rect.width+13,4,rect.width-200);
    tip.style.left=`${tipX}px`;
    tip.style.top=`${clamp((frame.y(value)/frame.height)*rect.height-62,10,rect.height-67)}px`;
  });
  svg.addEventListener('mouseleave',()=>{tip.style.display='none';rule.setAttribute('visibility','hidden');dot.setAttribute('visibility','hidden');});
}

export function renderHistory(container, data, currency='USD') {
  const rows=data||[];
  if(rows.length<2){container.innerHTML='<div class="loading-state">Not enough history for a chart.</div>';return;}
  const values=rows.flatMap(r=>[r.close, r.sma50]).filter(v=>Number.isFinite(v));
  const fr=chartFrame(container,Math.min(...values),Math.max(...values),rows.map(r=>r.date),{color:'#29ddcb',gradient:'historyFill'});
  const {svg,x,y,graphH,box}=fr, closes=rows.map(r=>r.close);
  const path=line(closes,x,y);
  const area=`${path} L${x(rows.length-1).toFixed(2)},${(box.top+graphH).toFixed(2)} L${x(0).toFixed(2)},${(box.top+graphH).toFixed(2)} Z`;
  svg.append(svgEl('path',{d:area,fill:'url(#historyFill)'}));
  const maxVol=Math.max(1,...rows.map(r=>r.volume));
  const groupSize=Math.max(1,Math.ceil(rows.length/100));
  for(let start=0;start<rows.length;start+=groupSize){
    const sample=rows.slice(start,start+groupSize);
    const avg=sample.reduce((s,r)=>s+r.volume,0)/sample.length;
    const barH=avg/maxVol*graphH*.11;
    const xx=x(start),end=x(Math.min(rows.length-1,start+groupSize));
    svg.append(svgEl('rect',{x:xx,y:box.top+graphH-barH,width:Math.max(1,end-xx-1),height:barH,fill:'#416d80',opacity:'.20'}));
  }
  const maSegments=[],current=[];
  rows.forEach((r,i)=>{if(r.sma50==null){if(current.length){maSegments.push([...current]);current.length=0;}}else current.push([i,r.sma50]);});
  if(current.length) maSegments.push(current);
  for(const segment of maSegments) svg.append(svgEl('path',{d:segment.map(([i,v],k)=>`${k?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' '),fill:'none',stroke:'#f2b95e','stroke-width':'1.6',opacity:'.8'}));
  svg.append(svgEl('path',{d:path,fill:'none',stroke:'#29ddcb','stroke-width':'2.6','stroke-linejoin':'round','stroke-linecap':'round'}));
  installTooltip(container,fr,rows,currency,{value:r=>r.close,label:()=> 'Close',extra:r=>`\nVolume: ${shortNum(r.volume)}`});
}

export function renderForecast(container, history, forecast, currency='USD') {
  if(!history?.length || !forecast?.length){container.innerHTML='<div class="loading-state">Forecast unavailable.</div>';return;}
  const past=history.slice(-90);
  const combined=[...past,...forecast];
  const bounds=[...past.map(r=>r.close),...forecast.flatMap(r=>[r.lower,r.upper])];
  const fr=chartFrame(container,Math.min(...bounds),Math.max(...bounds),combined.map(r=>r.date),{color:'#ad98ff',gradient:'forecastFill'});
  const {svg,x,y,graphH,box}=fr, at=past.length-1;
  const areaUpper=[[at,past.at(-1).close],...forecast.map((r,i)=>[at+i+1,r.upper])];
  const areaLower=[[at,past.at(-1).close],...forecast.map((r,i)=>[at+i+1,r.lower])].reverse();
  const band=[...areaUpper,...areaLower].map(([i,v],index)=>`${index?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ')+' Z';
  svg.append(svgEl('path',{d:band,fill:'#8d76f8','fill-opacity':'.17',stroke:'none'}));
  svg.append(svgEl('line',{x1:x(at),x2:x(at),y1:box.top,y2:box.top+graphH,stroke:'#77849e','stroke-dasharray':'4 5',opacity:'.65'}));
  const now=svgEl('text',{x:x(at)+6,y:box.top+13,fill:'#9bb0c5','font-size':10,'font-family':'Manrope, sans-serif'});now.textContent='TODAY';svg.append(now);
  const pastPath=line(past.map(r=>r.close), i=>x(i),y);
  svg.append(svgEl('path',{d:pastPath,fill:'none',stroke:'#29ddcb','stroke-width':'2.6','stroke-linejoin':'round'}));
  const futurePath=line([past.at(-1).close,...forecast.map(r=>r.predicted)], i=>x(at+i),y);
  svg.append(svgEl('path',{d:futurePath,fill:'none',stroke:'#b5a0ff','stroke-width':'2.5','stroke-dasharray':'7 5','stroke-linecap':'round','stroke-linejoin':'round'}));
  const tooltipRows=[...past.map(r=>({date:r.date,value:r.close,future:false})),...forecast.map(r=>({date:r.date,value:r.predicted,future:true,lower:r.lower,upper:r.upper}))];
  installTooltip(container,fr,tooltipRows,currency,{value:r=>r.value,label:r=>r.future?'Predicted':'Actual',extra:r=>r.future?`\nRange: ${moneyShort(r.lower,currency)} – ${moneyShort(r.upper,currency)}`:''});
}

export function renderAnnual(container, years) {
  container.replaceChildren();
  if(!years?.length){container.textContent='No annual returns available.';return;}
  const selected=years.slice(-9);
  const range=Math.max(5,...selected.map(y=>Math.abs(y.return_pct)));
  for(const item of selected){
    const col=document.createElement('div');col.className='annual-column';col.title=`${item.year}: ${item.return_pct>=0?'+':''}${item.return_pct.toFixed(2)}% (${item.sessions} sessions)`;
    const value=document.createElement('div');value.className=`annual-value ${item.return_pct>=0?'positive':'negative'}`;value.textContent=`${item.return_pct>0?'+':''}${item.return_pct.toFixed(1)}%`;
    const track=document.createElement('div');track.className='annual-track';
    const bar=document.createElement('div');bar.className=`annual-bar${item.return_pct<0?' negative':''}`;
    const h=Math.max(2,Math.abs(item.return_pct)/range*77);
    bar.style.height=`${h}px`;bar.style.top=item.return_pct>=0?`${83-h}px`:'83px';track.append(bar);
    const year=document.createElement('div');year.className='annual-year';year.textContent=String(item.year);
    col.append(value,track,year);container.append(col);
  }
}

export function showLoading(container, message='Calculating...') {
  container.innerHTML=`<div class="loading-state"><span class="spinner"></span>${message}</div>`;
}
