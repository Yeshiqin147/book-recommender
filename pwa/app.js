/* 阅荐 · 书籍推荐 —— 前端逻辑
   数据：books.json（本地打包）
   功能：搜索(中英文子串) / 分类筛选(内容·风格·篇幅) / 浏览记录(localStorage) / 行为推荐 / 详情弹窗 / 样式封面
   推荐逻辑内置在客户端，页面只呈现"为你推荐"，不暴露内部计算。
*/
"use strict";

const STORE = "yj_behavior";
const SLOG = "yj_search_log";

// ---------- 封面配色 ----------
const CN_COLORS = {
  "文学":"#5B8DB8","科幻":"#3E7CB1","历史":"#9A6B4F","社科":"#6B8E5A",
  "商业":"#C77E4B","心理":"#7D6BA6","散文":"#8FA6A0","古典":"#A0522D",
  "热门":"#C2574E","童书":"#E8A87C","科普":"#4E8D7C","哲学":"#5A5A7A",
  "奇幻":"#8E6CA8","经济":"#C77E4B","悬疑":"#6D597A",
};
const EN_COLORS = [
  "#2E86AB","#B23A48","#3A7D44","#9C6644","#5D576B",
  "#2C7DA0","#8A5A44","#6D597A","#4E8098","#B08D57",
];
// 简单 crc32
function crc32(str){
  let crc = 0xFFFFFFFF;
  for(let i=0;i<str.length;i++){
    crc ^= str.charCodeAt(i);
    for(let k=0;k<8;k++) crc = (crc>>>1) ^ (0xEDB88320 & -(crc & 1));
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
// 搜索归一化：忽略间隔号(·・•)与空白，让"哈利波特"能命中"哈利·波特"
function fold(s){ return String(s==null?"":s).toLowerCase().replace(/[·・•\s]/g,""); }

let BOOKS = [];
let BY_ISBN = new Map();
// 当前筛选状态
const state = {cat:"全部", style:"全部", length:"全部"};

async function loadData(){
  const r = await fetch("books.json", {cache:"no-store"});
  const data = await r.json();
  BOOKS = data.books;
  for(const b of BOOKS) BY_ISBN.set(b.isbn, b);
  renderAll();
}

// ---------- 封面（本地生成，不依赖外网） ----------
function coverHtml(b){
  const color = b.lang==="cn"
    ? (CN_COLORS[b.category] || "#5A5A7A")
    : EN_COLORS[crc32(b.isbn) % EN_COLORS.length];
  const chip = b.lang==="cn" ? "🇨🇳 "+b.category : "EN";
  return `<div class="cover" style="background:linear-gradient(150deg,${color},${color}cc)">
    <div class="chip">${esc(chip)}</div>
    <div class="ctitle">《${esc(b.title)}》</div>
    <div class="cauthor">${esc(b.author)}</div>
  </div>`;
}

// ---------- 存储 ----------
function getBehavior(){ try{return JSON.parse(localStorage.getItem(STORE)||"{}")}catch(e){return{}} }
function setBehavior(v){ localStorage.setItem(STORE, JSON.stringify(v)) }
function getSearchLog(){ try{return JSON.parse(localStorage.getItem(SLOG)||"[]")}catch(e){return[]} }
function setSearchLog(v){ localStorage.setItem(SLOG, JSON.stringify(v)) }

function logView(isbn){
  const beh = getBehavior();
  const now = Date.now()/1000;
  if(beh[isbn]){ beh[isbn].clicks++; beh[isbn].dwell = Math.min((beh[isbn].dwell||0) + Math.min(Math.max(now-(beh[isbn].ts||now),0),300), 900); }
  else beh[isbn] = {clicks:1, dwell:0};
  beh[isbn].ts = now;
  setBehavior(beh);
}
function logSearch(term){
  term = (term||"").trim();
  if(!term) return;
  const log = getSearchLog();
  if(!log.length || log[log.length-1].toLowerCase()!==term.toLowerCase()){
    log.push(term);
    setSearchLog(log.slice(-10));
  }
}

// ---------- 行为推荐（内置逻辑，复刻服务端口径） ----------
function recommend(behavior, searchLog, n){
  behavior = behavior||{};
  const interacted = new Set(Object.keys(behavior));
  const score = new Map();
  const add = (isbn,v)=>score.set(isbn,(score.get(isbn)||0)+v);
  for(const [isbn, info] of Object.entries(behavior)){
    const book = BY_ISBN.get(isbn); if(!book) continue;
    const w = (0.5 + 0.15*(info.clicks||1)) * Math.min(1 + (info.dwell||0)/60, 3);
    if(book.category) for(const b of BOOKS) if(b.category===book.category) add(b.isbn, w*2.0);
    if(book.author)   for(const b of BOOKS) if(b.author===book.author) add(b.isbn, w*1.5);
  }
  for(const t of (searchLog||[])){
    const s = String(t).trim().toLowerCase(); if(!s) continue;
    const fs = fold(s);
    for(const b of BOOKS){
      if(fold(b.title).includes(fs) || fold(b.title_zh).includes(fs)
        || fold(b.author).includes(fs)
        || fold(b.publisher).includes(fs) || fold(b.category).includes(fs))
        add(b.isbn, 1.0);
    }
  }
  for(const b of BOOKS) add(b.isbn, 0.25*b.pop);
  return BOOKS.filter(b=>!interacted.has(b.isbn))
    .sort((a,b)=>(score.get(b.isbn)||0)-(score.get(a.isbn)||0))
    .slice(0, n);
}

function searchBooks(kw){
  kw = (kw||"").trim().toLowerCase();
  if(!kw) return [];
  const fk = fold(kw);
  return BOOKS.filter(b=>fold(b.title).includes(fk)
    || fold(b.title_zh).includes(fk)
    || fold(b.author).includes(fk)
    || fold(b.publisher).includes(fk)
    || fold(b.category).includes(fk));
}

// ---------- 分类筛选 ----------
function uniqOptions(key){
  const m = new Map();
  for(const b of BOOKS){ const v=b[key]||"其他"; m.set(v,(m.get(v)||0)+1); }
  return [...m.entries()].sort((a,b)=>b[1]-a[1]);
}
function applyFilter(list){
  return list.filter(b=>
    (state.cat==="全部" || (b.category||"其他")===state.cat) &&
    (state.style==="全部" || (b.style||"小说")===state.style) &&
    (state.length==="全部" || (b.length||"长篇")===state.length)
  );
}
function chipRow(label, key, cur){
  const opts = uniqOptions(key);
  let h = `<div class="filter-row"><span class="filter-label">${label}</span>`;
  h += `<span class="fchip ${cur==="全部"?"on":""}" data-dim="${key}" data-v="全部">全部</span>`;
  for(const [v] of opts){
    h += `<span class="fchip ${cur===v?"on":""}" data-dim="${key}" data-v="${esc(v)}">${esc(v)}</span>`;
  }
  return h + `</div>`;
}
function filterBarHtml(){
  return `<div class="filter-bar">
    ${chipRow("内容","cat",state.cat)}
    ${chipRow("风格","style",state.style)}
    ${chipRow("篇幅","length",state.length)}
  </div>`;
}

// ---------- 渲染 ----------
const main = document.getElementById("main");
const searchInput = document.getElementById("search-input");
const historyEl = document.getElementById("history");

function stars(b){
  if(!b.rating || b.rating<=0) return "";
  return `⭐ ${b.rating.toFixed(1)}`;
}
// 网格小卡片：封面为主
function itemHtml(b, rank){
  const rk = rank!=null ? `<span style="position:absolute;top:4px;left:6px;font-size:11px;font-weight:700;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5);z-index:2">#${rank}</span>` : "";
  const st = stars(b);
  const rc = b.rc>0 ? ` · ${b.rc>=10000?(b.rc/10000).toFixed(1)+"万":b.rc}` : "";
  return `<div class="book-item" data-isbn="${esc(b.isbn)}">
    <div style="position:relative">${rk}${coverHtml(b)}</div>
    <div class="bi-title">${esc(b.title_zh||b.title)}</div>
    <div class="bi-meta">${st?`<span class="stars">${st}</span>`:""}<span>${rc}</span></div>
  </div>`;
}
function section(title, sub){
  return `<div class="section-title">${title}${sub?`<span class="sub">${sub}</span>`:""}</div>`;
}
function empty(text){
  return `<div class="empty">${text}</div>`;
}

function renderHistory(){
  const beh = getBehavior();
  const keys = Object.keys(beh);
  historyEl.innerHTML = keys.length
    ? keys.map(k=>{
        const b = BY_ISBN.get(k); if(!b) return "";
        return `<span class="tag" data-open="${esc(k)}">${esc(b.title)}</span>`;
      }).join("")
    : `<span style="color:var(--sub);font-size:12px">点开一本书会自动加入浏览记录</span>`;
}

function renderGrid(list, startRank){
  if(!list.length) return empty("这一类暂时没有书，换个筛选看看");
  return `<div class="book-grid">${list.map((b,i)=>itemHtml(b, startRank!=null?startRank+i:null)).join("")}</div>`;
}

function renderAll(){
  const beh = getBehavior();
  const slog = getSearchLog();
  const hasBehavior = Object.keys(beh).length>0 || slog.length>0;
  const kw = searchInput.value.trim();

  let html = filterBarHtml();
  if(kw){
    logSearch(kw);
    const hits = applyFilter(searchBooks(kw));
    html += section("搜索结果", `${hits.length} 本`);
    html += hits.length ? renderGrid(hits) : empty("没有找到匹配的书，换个关键词试试");
  } else if(hasBehavior){
    const recs = applyFilter(recommend(beh, slog, 40));
    html += section("🎯 为你推荐", "根据你搜过、看过的书挑选");
    html += recs.length ? renderGrid(recs) : empty("再点开几本书，或换个筛选条件");
  } else {
    const hot = applyFilter([...BOOKS].sort((a,b)=>b.pop-a.pop).slice(0,18));
    if(hot.length){
      html += section("🔥 大家都在读", "热门书精选");
      html += renderGrid(hot);
    }
    const cn = applyFilter(BOOKS.filter(b=>b.lang==="cn").sort((a,b)=>b.rating-a.rating).slice(0,18));
    if(cn.length){
      html += section("🇨🇳 中文高分精选", "真实豆瓣高分书，点开看详情");
      html += renderGrid(cn);
    }
  }
  main.innerHTML = html;
  renderHistory();
}

// ---------- 详情弹窗 ----------
const overlay = document.getElementById("overlay");
const modal = document.getElementById("modal");
function openDetail(isbn){
  const b = BY_ISBN.get(isbn); if(!b) return;
  logView(isbn);
  const s = stars(b);
  const rc = b.rc>0 ? ` · ${b.rc.toLocaleString()} 人评分` : "";
  const tags = [b.category, b.style, b.length].filter(Boolean).map(t=>`<span class="t">${esc(t)}</span>`).join("");
  const lang = b.lang==="cn" ? "中文" : "英文";
  const descBlock = b.desc
    ? `<div class="desc-block"><h4>内容简介</h4><div class="desc-body">${esc(b.desc)}</div></div>`
    : `<div class="desc-block"><h4>内容简介</h4><div class="desc-body" style="color:var(--sub)">（本书暂无简介）</div></div>`;
  modal.innerHTML = `
    <div class="modal-head">
      ${coverHtml(b)}
      <div style="flex:1;min-width:0">
        <h2>《${esc(b.title_zh||b.title)}》${b.title_zh&&b.title!==b.title_zh?`<div class="meta" style="margin-top:2px">原名：${esc(b.title)}</div>`:""}</h2>
        <div class="meta">作者：${esc(b.author)}</div>
        <div class="meta">出版社：${esc(b.publisher)}（${b.year}）</div>
        <div class="meta">语言：${lang} · ISBN：${esc(b.isbn)}</div>
        <div class="tags">${tags}</div>
        <div class="stars" style="color:#c77e2e;margin-top:6px">${s}${rc}</div>
      </div>
    </div>
    ${descBlock}
    <button class="modal-close">关 闭</button>`;
  overlay.hidden = false;
}

// ---------- 事件绑定 ----------
let debounce;
searchInput.addEventListener("input", ()=>{
  clearTimeout(debounce);
  debounce = setTimeout(renderAll, 150);
});

main.addEventListener("click", (e)=>{
  // 分类标签
  const chip = e.target.closest(".fchip");
  if(chip){
    state[chip.dataset.dim] = chip.dataset.v;
    renderAll();
    return;
  }
  const item = e.target.closest(".book-item");
  if(item) openDetail(item.dataset.isbn);
});
historyEl.addEventListener("click", (e)=>{
  const tag = e.target.closest(".tag");
  if(tag) openDetail(tag.dataset.open);
});
overlay.addEventListener("click", (e)=>{
  if(e.target===overlay || e.target.classList.contains("modal-close")) overlay.hidden = true;
});
document.getElementById("clear-btn").addEventListener("click", ()=>{
  localStorage.removeItem(STORE);
  localStorage.removeItem(SLOG);
  renderAll();
  toast("已清空浏览记录");
});

function toast(msg){
  let t = document.querySelector(".toast");
  if(!t){ t = document.createElement("div"); t.className="toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(()=>t.classList.remove("show"), 1600);
}

// ---------- 启动 ----------
loadData();
