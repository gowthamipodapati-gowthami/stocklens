import {fetchSymbols, fetchDashboard, fetchForecast} from './api.js';
import {renderHistory, renderForecast, renderAnnual, showLoading} from './charts.js';

const byId = id => document.getElementById(id);
const state={symbol:'DEMO',period:'5y',days:30,history:null,prediction:null,requestId:0,
             symbols:[],watchlist:['DEMO','AAPL','NVDA','MSFT','RELIANCE.NS','TCS.NS']};
let toastTimer;

const currencyFormat = (num,currency='USD',maximumFractionDigits=2) =>
  num==null||!Number.isFinite(Number(num)) ? '—' : new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits}).format(num);
const percent = num => num==null||!Number.isFinite(Number(num)) ? '—' : `${num>0?'+':''}${Number(num).toFixed(2)}%`;
const integer = num => num==null ? '—' : Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(num);
const set = (id, value) => {byId(id).textContent = value;};
const colored = (id, value) => {const el=byId(id);el.classList.remove('value-positive','value-negative');if(Number(value)>0)el.classList.add('value-positive');if(Number(value)<0)el.classList.add('value-negative');};

function toast(message,error=false){const el=byId('toast');el.textContent=message;el.className=`toast visible${error?' error':''}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='toast',6500);}
function setLoading(loading){byId('analyzeButton').disabled=loading;byId('analyzeButton').firstChild.textContent=loading?'Loading stock ':'Analyze stock ';}
function renderTabs(){document.querySelectorAll('#periodTabs button').forEach(btn=>btn.classList.toggle('selected',btn.dataset.period===state.period));document.querySelectorAll('#forecastTabs button').forEach(btn=>btn.classList.toggle('selected',Number(btn.dataset.days)===state.days));}

function renderWatchlist(){
  const host=byId('watchlist');host.replaceChildren();
  for(const ticker of state.watchlist){
    const known=state.symbols.find(s=>s.symbol===ticker);
    const button=document.createElement('button');button.type='button';button.className=`watch-item${ticker===state.symbol?' active':''}`;
    const icon=document.createElement('span');icon.className='watch-icon';icon.textContent=ticker==='DEMO'?'◈':ticker.slice(0,1);
    const info=document.createElement('span');info.className='watch-copy';const title=document.createElement('b');title.textContent=ticker;const sub=document.createElement('span');sub.textContent=known?.name||'Custom ticker';info.append(title,sub);
    const arrow=document.createElement('span');arrow.className='watch-arrow';arrow.textContent='↗';button.append(icon,info,arrow);
    button.addEventListener('click',()=>analyze(ticker));host.append(button);
  }
}

function showDashboard(d){
  const curr=d.currency;
  set('companyName',d.name);set('companySymbol',d.symbol);set('companyIcon',d.symbol==='DEMO'?'✳':d.symbol.slice(0,1));
  set('lastTradeDate',`As of ${d.last_date}`);set('sessionsCount',`${integer(d.total_sessions)} sessions`);
  const badge=byId('sourceBadge');const demo=d.source==='synthetic_demo';badge.textContent=demo?'SYNTHETIC DEMO':'YAHOO FINANCE';badge.classList.toggle('live',!demo);
  set('mainPrice',currencyFormat(d.latest_close,curr));set('dailyChange',`${d.change_pct>=0?'↗':'↘'} ${percent(d.change_pct)}`);
  byId('dailyChange').classList.toggle('down',d.change_pct<0);
  set('priceCurrency',`Adjusted closing prices · ${curr}`);
  set('periodReturn',percent(d.period_return_pct));colored('periodReturn',d.period_return_pct);
  set('periodReturnHint',`${state.period.toUpperCase()} selected range`);
  set('cagr',percent(d.cagr_pct));colored('cagr',d.cagr_pct);
  set('volatility',percent(d.annualized_volatility_pct));
  set('drawdown',percent(d.max_drawdown_pct));colored('drawdown',d.max_drawdown_pct);
  set('high52',currencyFormat(d.high_52w,curr));set('low52',currencyFormat(d.low_52w,curr));
  set('sma50',currencyFormat(d.sma50,curr));set('avgVolume',integer(d.average_volume_30d));
  set('priceChartDateRange',`${d.history[0]?.date||''} — ${d.last_date}`);
  const trend=d.trend_vs_sma50==='above'?'Price is above its 50-day moving average':d.trend_vs_sma50==='below'?'Price is below its 50-day moving average':'Insufficient data for the 50-day trend';
  set('trendDescription',trend);const square=document.querySelector('.square-indicator');square.classList.toggle('negative',d.trend_vs_sma50==='below');square.classList.toggle('positive',d.trend_vs_sma50!=='below');
  set('priceDataNote',demo?'ALL VALUES ON THIS CHART ARE SYNTHETIC':'Delayed historical daily data · Not real-time quotes');
  renderHistory(byId('historyChart'),d.history,curr);renderAnnual(byId('annualChart'),d.years);
}

function showForecast(f){
  const curr=state.history?.currency||'USD';const end=f.points.at(-1);if(!end)return;
  const change=(end.predicted/f.base_close-1)*100;
  set('forecastPrice',currencyFormat(end.predicted,curr));set('forecastChange',percent(change));
  byId('forecastChange').classList.toggle('down',change<0);
  set('forecastLower',currencyFormat(end.lower,curr));set('forecastUpper',currencyFormat(end.upper,curr));
  set('forecastMae',currencyFormat(f.mae,curr));set('forecastBaseline',currencyFormat(f.baseline_mae,curr));
  set('forecastModel',f.model_name);set('forecastDate',`${f.days} weekdays ahead · ${end.date} · tested on ${f.validation_points} sessions`);
  renderForecast(byId('forecastChart'),state.history.history,f.points,curr);
}

async function analyze(rawSymbol, opts={}){
  const ticker=String(rawSymbol||'').trim().toUpperCase();
  if(!/^[A-Z0-9^][A-Z0-9.\-^=]{0,19}$/.test(ticker)){toast('Enter a valid ticker, e.g. AAPL or TCS.NS.',true);return;}
  const ticket=++state.requestId;state.symbol=ticker;state.history=null;state.prediction=null;byId('tickerInput').value=ticker;renderWatchlist();setLoading(true);
  showLoading(byId('historyChart'),'Loading historical market data...');showLoading(byId('forecastChart'),'Forecasting...');
  try{
    const dashboard=await fetchDashboard(ticker,state.period,opts.refresh||false);
    if(ticket!==state.requestId)return;
    state.history=dashboard;state.prediction=null;showDashboard(dashboard);renderWatchlist();
    if(!state.watchlist.includes(ticker)){state.watchlist=[ticker,...state.watchlist].slice(0,8);renderWatchlist();}
    set('forecastPrice','Calculating...');
    try{
      const f=await fetchForecast(ticker,state.days);
      if(ticket!==state.requestId)return;
      state.prediction=f;showForecast(f);
    }catch(error){if(ticket===state.requestId){byId('forecastChart').innerHTML='<div class="loading-state">Forecast unavailable for this ticker.</div>';set('forecastPrice','Unavailable');toast(error.message,true);}}
  }catch(error){
    if(ticket===state.requestId){byId('historyChart').innerHTML='<div class="loading-state">Could not retrieve market data. Try another ticker or DEMO.</div>';byId('forecastChart').innerHTML='<div class="loading-state">No forecast</div>';toast(error.message,true);}
  }finally{if(ticket===state.requestId)setLoading(false);}
}

async function changePeriod(period){if(state.period===period)return;state.period=period;renderTabs();
  const ticket=++state.requestId;setLoading(true);showLoading(byId('historyChart'),'Loading chart...');
  try{const d=await fetchDashboard(state.symbol,period);if(ticket!==state.requestId)return;state.history=d;showDashboard(d);if(state.prediction)showForecast(state.prediction);}
  catch(error){if(ticket===state.requestId)toast(error.message,true);}finally{if(ticket===state.requestId)setLoading(false);}
}
async function changeDays(days){if(state.days===days)return;state.days=days;renderTabs();const ticket=++state.requestId;
  showLoading(byId('forecastChart'),'Running forecast...');
  try{const data=await fetchForecast(state.symbol,days);if(ticket!==state.requestId)return;state.prediction=data;showForecast(data);}
  catch(error){if(ticket===state.requestId)toast(error.message,true);}
}

byId('searchForm').addEventListener('submit',e=>{e.preventDefault();analyze(byId('tickerInput').value);});
document.querySelectorAll('[data-symbol]').forEach(btn=>btn.addEventListener('click',()=>analyze(btn.dataset.symbol)));
byId('periodTabs').addEventListener('click',e=>{if(e.target.dataset.period)changePeriod(e.target.dataset.period);});
byId('forecastTabs').addEventListener('click',e=>{if(e.target.dataset.days)changeDays(Number(e.target.dataset.days));});
byId('resetWatchlist').addEventListener('click',()=>{state.watchlist=['DEMO','AAPL','NVDA','MSFT','RELIANCE.NS','TCS.NS'];renderWatchlist();toast('Suggested symbols restored.');});
byId('menuButton').addEventListener('click',()=>byId('sidebar').classList.toggle('open'));
document.querySelectorAll('.nav-item').forEach(a=>a.addEventListener('click',()=>{document.querySelectorAll('.nav-item').forEach(el=>el.classList.remove('active'));a.classList.add('active');byId('sidebar').classList.remove('open');}));
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(state.history)renderHistory(byId('historyChart'),state.history.history,state.history.currency);if(state.prediction&&state.history)renderForecast(byId('forecastChart'),state.history.history,state.prediction.points,state.history.currency);},130);});
byId('currentYear').textContent=new Date().getFullYear();
fetchSymbols().then(({symbols})=>{state.symbols=symbols;renderWatchlist();}).catch(()=>renderWatchlist());
analyze('DEMO');
