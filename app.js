/* 阅荐 · 书籍推荐 —— 前端逻辑
   数据：books.json（本地打包）
   功能：搜索(中英文子串) / 浏览记录(localStorage) / 行为推荐 / 详情弹窗 / 样式封面
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

let BOOKS = [];
let BY_ISBN = new Map();

async function loadData(){
  const r = await fetch("books.json", {cache:"no-store"});
  const data = await r.json();
  BOOKS = data.books;
  for(const b of BOOKS) BY_ISBN.set(b.isbn, b);
  renderAll();
}

// ---------- 封面（本地生成，不依赖外网） ----------
function coverHtml(b, w, h){
  const color = b.lang==="cn"
    ? (CN_COLORS[b.category] || "#5A5A7A")
    : EN_COLORS[crc32(b.isbn) % EN_COLORS.length];
  const chip = b.lang==="cn" ? "🇨🇳 "+b.category : "EN";
  const fs = w>=110 ? 13 : 11;
  return `<div class="cover" style="width:${w}px;height:${h}px;background:linear-gradient(150deg,${color},${color}cc)">
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
    for(const b of BOOKS){
      if(b.title.toLowerCase().includes(s) || b.author.toLowerCase().includes(s)
        || b.publisher.toLowerCase().includes(s) || (b.category||"").toLowerCase().includes(s))
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
  return BOOKS.filter(b=>b.title.toLowerCase().includes(kw)
    || b.author.toLowerCase().includes(kw)
    || b.publisher.toLowerCase().includes(kw)
    || (b.category||"").toLowerCase().includes(kw))
    .slice(0, 60);
}

// ---------- 渲染 ----------
const main = document.getElementById("main");
const searchInput = document.getElementById("search-input");
const historyEl = document.getElementById("history");

function stars(rating){
  if(!rating || rating<=0) return "";
  return "⭐ "+rating.toFixed(1);
}
function langChip(b){
  return b.lang==="cn" ? '<span class="chip-lang chip-cn">中文</span>' : '<span class="chip-lang chip-en">英文</span>';
}
function cardHtml(b, rank){
  const s = stars(b.rating);
  const rc = b.rc>0 ? ` · ${b.rc.toLocaleString()} 人评分` : "";
  const desc = b.desc ? `<div class="desc">${esc(b.desc.slice(0,80))}${b.desc.length>80?"…":""}</div>` : "";
  const rk = rank!=null ? `<span style="color:${EN_COLORS[rank-1]||"#888"}">#${rank}</span> ` : "";
  return `<div class="book-card" data-isbn="${esc(b.isbn)}">
    ${coverHtml(b,76,112)}
    <div class="book-info">
      <h3>${rk}${langChip(b)}《${esc(b.title)}》</h3>
      <div class="meta">${esc(b.author)} · ${b.year}</div>
      <div class="meta">${esc(b.publisher)}</div>
      <div class="stars">${s}${rc}</div>
      ${desc}
    </div>
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

function renderAll(){
  const beh = getBehavior();
  const slog = getSearchLog();
  const hasBehavior = Object.keys(beh).length>0 || slog.length>0;
  const kw = searchInput.value.trim();

  let html = "";
  if(kw){
    logSearch(kw);
    const hits = searchBooks(kw);
    html += section("搜索结果", `${hits.length} 条`);
    html += hits.length ? hits.map(cardHtml).join("") : empty("没有找到匹配的书，换个关键词试试");
  } else if(hasBehavior){
    const recs = recommend(beh, slog, 8);
    html += section("🎯 为你推荐", "根据你搜过、看过的书挑选");
    html += recs.length ? recs.map((b,i)=>cardHtml(b,i+1)).join("") : empty("再点开几本书，推荐会更准");
  } else {
    const hot = [...BOOKS].sort((a,b)=>b.pop-a.pop).slice(0,6);
    html += section("🔥 大家都在读", "热门书精选");
    html += hot.map((b,i)=>cardHtml(b,i+1)).join("");
    const cn = BOOKS.filter(b=>b.lang==="cn").sort((a,b)=>b.rating-a.rating).slice(0,8);
    html += section("🇨🇳 中文书目精选", "真实豆瓣高分书，点开看详情");
    html += cn.map((b,i)=>cardHtml(b,i+1)).join("");
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
  const s = stars(b.rating);
  const rc = b.rc>0 ? ` · ${b.rc.toLocaleString()} 人评分` : "";
  const cate = b.category ? `<div class="meta">分类：${esc(b.category)}</div>` : "";
  const lang = b.lang==="cn" ? "中文" : "英文";
  const descBlock = b.desc
    ? `<div class="desc-block"><h4>内容简介</h4><div class="desc-body">${esc(b.desc)}</div></div>`
    : `<div class="desc-block"><h4>内容简介</h4><div class="desc-body" style="color:var(--sub)">（本书暂无简介）</div></div>`;
  modal.innerHTML = `
    <div class="modal-head">
      ${coverHtml(b,96,142)}
      <div style="flex:1;min-width:0">
        <h2>《${esc(b.title)}》</h2>
        <div class="meta">作者：${esc(b.author)}</div>
        <div class="meta">出版社：${esc(b.publisher)}（${b.year}）</div>
        <div class="meta">语言：${lang} · ISBN：${esc(b.isbn)}</div>
        ${cate}
        <div class="stars">${s}${rc}</div>
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
  const card = e.target.closest(".book-card");
  if(card) openDetail(card.dataset.isbn);
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
