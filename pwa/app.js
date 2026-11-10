/* 阅荐言情 · 前端
   首屏问卷 + Netflix式横向卡片流 + 言情细分标签
*/
"use strict";

const STORE = "yj_pref";
const BEHAVIOR = "yj_behavior_v2";

function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function fold(s){ return String(s==null?"":s).toLowerCase().replace(/[·・•\s]/g,""); }
function crc32(str){ let c=0xFFFFFFFF; for(let i=0;i<str.length;i++){ c^=str.charCodeAt(i); for(let k=0;k<8;k++) c=(c>>>1)^(0xEDB88320&-(c&1)); } return (c^0xFFFFFFFF)>>>0; }

let BOOKS = [];
let BY_ISBN = new Map();

// ---------- 封面配色（言情粉系） ----------
const ROMANCE_COLORS = [
  "#e91e63","#ad1457","#c2185b","#d81b60","#ec407a",
  "#f06292","#f48fb1","#880e4f","#a0206b","#b83a6e",
];
const SUBCAT_COLORS = {
  "古言":"#ad1457","现言":"#e91e63","仙侠":"#7b1fa2","穿越":"#00897b",
  "甜宠":"#f06292","虐文":"#5d4037","霸总":"#263238","校园":"#42a5f5",
  "职场":"#6d4c41","宫斗":"#880e4f","宅斗":"#6a1b9a","耽美":"#00838f",
  "百合":"#00acc1","西方":"#5c6bc0","悬疑":"#455a64","奇幻":"#6d597a",
};

function coverHtml(b){
  const color = SUBCAT_COLORS[b.subcat] || ROMANCE_COLORS[crc32(b.isbn) % ROMANCE_COLORS.length];
  return `<div class="cover" style="background:linear-gradient(160deg,${color} 0%,${color}dd 100%)">
    <div class="ctitle">《${esc(b.title_zh||b.title)}》</div>
    <div class="cauthor">${esc(b.author)}</div>
  </div>`;
}

// ---------- 偏好 ----------
function getPref(){ try{return JSON.parse(localStorage.getItem(STORE)||"null")}catch(e){return null} }
function setPref(v){ localStorage.setItem(STORE, JSON.stringify(v)) }
function getBehavior(){ try{return JSON.parse(localStorage.getItem(BEHAVIOR)||"{}")}catch(e){return{}} }
function setBehavior(v){ localStorage.setItem(BEHAVIOR, JSON.stringify(v)) }

function logView(isbn){
  const beh = getBehavior();
  if(beh[isbn]) beh[isbn]++; else beh[isbn] = 1;
  setBehavior(beh);
}

// ---------- 首屏问卷 ----------
const OB_STEPS = [
  {
    title: "你喜欢哪种类型的爱情故事？",
    sub: "可多选，选你感兴趣的",
    multi: true,
    key: "types",
    options: [
      {v:"古言", icon:"🏯", label:"古代言情", desc:"宫廷、宅斗、江湖"},
      {v:"现言", icon:"🏙️", label:"现代言情", desc:"都市、职场、校园"},
      {v:"仙侠", icon:"🐉", label:"仙侠奇缘", desc:"修真、玄幻、前世今生"},
      {v:"穿越", icon:"⏰", label:"穿越重生", desc:"穿书、重生、时空交错"},
      {v:"耽美", icon:"💫", label:"耽美纯爱", desc:"男男情感"},
      {v:"百合", icon:"🌸", label:"百合", desc:"女女情感"},
    ]
  },
  {
    title: "你偏爱的甜度是？",
    sub: "单选，影响推荐口味",
    multi: false,
    key: "vibe",
    options: [
      {v:"甜宠", icon:"🍬", label:"甜宠", desc:"全程高甜，撒狗粮"},
      {v:"虐恋", icon:"💔", label:"虐恋", desc:"先虐后甜，意难平"},
      {v:"强强", icon:"⚔️", label:"强强对决", desc:"势均力敌，斗智斗勇"},
      {v:"都行", icon:"🎲", label:"都可以", desc:"不挑，好看就行"},
    ]
  },
  {
    title: "你看文的习惯是？",
    sub: "单选",
    multi: false,
    key: "length",
    options: [
      {v:"短篇", icon:"📖", label:"短篇", desc:"一口气看完"},
      {v:"长篇", icon:"📚", label:"长篇", desc:"追更，沉浸式"},
      {v:"中篇", icon:"📑", label:"中篇", desc:"周末读完"},
      {v:"都行", icon:"🎲", label:"都可以", desc:"看心情"},
    ]
  },
];

let obStep = 0;
let obAnswers = {};

function showOnboarding(){
  obStep = 0;
  obAnswers = {};
  document.getElementById("onboarding").hidden = false;
  renderObStep();
}

function renderObStep(){
  const step = OB_STEPS[obStep];
  document.getElementById("ob-title").textContent = step.title;
  document.getElementById("ob-sub").textContent = step.sub;
  document.getElementById("ob-back").hidden = obStep===0;

  let h = `<div class="ob-opts">`;
  for(const opt of step.options){
    const sel = obAnswers[step.key] && (step.multi ? obAnswers[step.key].includes(opt.v) : obAnswers[step.key]===opt.v);
    h += `<div class="ob-opt ${sel?"on":""}" data-v="${opt.v}">
      <span class="ob-icon">${opt.icon}</span>
      <div><div class="ob-label">${opt.label}</div><div class="ob-desc">${opt.desc}</div></div>
    </div>`;
  }
  h += `</div>`;
  document.getElementById("ob-body").innerHTML = h;

  document.getElementById("ob-next").textContent = obStep===OB_STEPS.length-1 ? "开始发现" : "下一步";
}

function finishOnboarding(){
  setPref(obAnswers);
  document.getElementById("onboarding").hidden = true;
  document.getElementById("retry-btn").hidden = false;
  updateGreeting();
  renderAll();
}

// ---------- 数据加载 ----------
async function loadData(){
  const r = await fetch("books.json", {cache:"no-store"});
  const data = await r.json();
  BOOKS = data.books;
  for(const b of BOOKS) BY_ISBN.set(b.isbn, b);

  const pref = getPref();
  if(!pref){
    showOnboarding();
  } else {
    document.getElementById("retry-btn").hidden = false;
    updateGreeting();
    renderAll();
  }
}

function updateGreeting(){
  const pref = getPref();
  if(!pref) return;
  const types = pref.types || [];
  const vibe = pref.vibe || "都行";
  document.getElementById("greeting").textContent =
    types.length ? `为你精选 ${types.join(" / ")} · ${vibe} 好文` : "发现你的下一本心动小说";
}

// ---------- 推荐逻辑 ----------
function scoreBook(b, pref){
  let s = b.pop * 10;
  const types = (pref && pref.types) || [];
  if(types.includes(b.subcat)) s += 50;
  if(types.length===0 || types.includes("都行")) s += 10;
  const vibe = (pref && pref.vibe) || "";
  if(vibe==="甜宠" && b.subcat==="甜宠") s += 30;
  if(vibe==="虐恋" && b.subcat==="虐文") s += 30;
  if(vibe==="强强" && (b.subcat==="强强"||b.subcat==="职场")) s += 20;
  const len = (pref && pref.length) || "";
  if(len && len!=="都行" && b.length===len) s += 15;
  // 行为加分
  const beh = getBehavior();
  if(beh[b.isbn]) s += beh[b.isbn] * 20;
  return s;
}

function recommendBooks(pref, n){
  return [...BOOKS].map(b=>({b, s:scoreBook(b, pref)}))
    .sort((a,b)=>b.s-a.s)
    .slice(0, n)
    .map(x=>x.b);
}

// ---------- 版块分组 ----------
function buildRows(pref){
  const rows = [];
  // 1. 为你推荐
  const recs = recommendBooks(pref, 20);
  if(recs.length) rows.push({title:"💘 为你推荐", books:recs});

  // 2. 按用户偏好类型分组
  const types = (pref && pref.types) || [];
  for(const t of types){
    const list = BOOKS.filter(b=>b.subcat===t).sort((a,b)=>b.pop-a.pop).slice(0,15);
    if(list.length) rows.push({title:`${subcatIcon(t)} ${subcatName(t)}`, books:list});
  }

  // 3. 热门总榜
  const hot = [...BOOKS].sort((a,b)=>b.pop-a.pop).slice(0,15);
  rows.push({title:"🔥 热门总榜", books:hot});

  // 4. 高分精选
  const rated = BOOKS.filter(b=>b.rating>0).sort((a,b)=>b.rating-a.rating).slice(0,15);
  rows.push({title:"⭐ 高分精选", books:rated});

  return rows;
}

function subcatIcon(t){
  return {"古言":"🏯","现言":"🏙️","仙侠":"🐉","穿越":"⏰","甜宠":"🍬","虐文":"💔",
    "霸总":"💼","校园":"🎓","职场":"💼","宫斗":"👑","宅斗":"🏠","耽美":"💫",
    "百合":"🌸","西方":"🌍","悬疑":"🔍","奇幻":"✨"}[t] || "📖";
}
function subcatName(t){
  return {"古言":"古代言情","现言":"现代言情","仙侠":"仙侠奇缘","穿越":"穿越重生",
    "甜宠":"甜宠合集","虐文":"虐恋专区","霸总":"霸总总裁","校园":"校园青春",
    "职场":"职场恋情","宫斗":"宫斗权谋","宅斗":"宅斗世家","耽美":"耽美纯爱",
    "百合":"百合之恋","西方":"西方浪漫","悬疑":"悬疑爱情","奇幻":"奇幻情缘"}[t] || t;
}

// ---------- 搜索 ----------
function searchBooks(kw){
  kw = (kw||"").trim().toLowerCase();
  if(!kw) return [];
  const fk = fold(kw);
  return BOOKS.filter(b=>fold(b.title).includes(fk) || fold(b.title_zh).includes(fk)
    || fold(b.author).includes(fk));
}

// ---------- 渲染 ----------
const main = document.getElementById("main");
const searchInput = document.getElementById("search-input");

function stars(b){
  if(!b.rating || b.rating<=0) return "";
  return `⭐ ${b.rating.toFixed(1)}`;
}

function cardHtml(b, rank){
  const rk = rank!=null ? `<span class="rank-badge">#${rank}</span>` : "";
  const st = stars(b);
  return `<div class="card" data-isbn="${esc(b.isbn)}">
    <div class="card-cover-wrap">${rk}${coverHtml(b)}</div>
    <div class="card-title">${esc(b.title_zh||b.title)}</div>
    <div class="card-author">${esc(b.author)}</div>
    ${st?`<div class="card-stars">${st}</div>`:""}
  </div>`;
}

function rowHtml(title, books){
  return `<div class="book-row">
    <div class="row-title">${title}</div>
    <div class="row-scroll">${books.map(b=>cardHtml(b)).join("")}</div>
  </div>`;
}

function renderAll(){
  const pref = getPref();
  const kw = searchInput.value.trim();

  let html = "";
  if(kw){
    const hits = searchBooks(kw);
    html += `<div class="row-title">🔍 搜索结果 · ${hits.length} 本</div>`;
    html += hits.length
      ? `<div class="row-scroll single">${hits.map((b,i)=>cardHtml(b,i+1)).join("")}</div>`
      : `<div class="empty">没有找到「${esc(kw)}」，换个关键词试试</div>`;
  } else {
    const rows = buildRows(pref);
    for(const r of rows){
      html += rowHtml(r.title, r.books);
    }
  }
  main.innerHTML = html;
}

// ---------- 详情 ----------
const overlay = document.getElementById("overlay");
const modal = document.getElementById("modal");

function openDetail(isbn){
  const b = BY_ISBN.get(isbn); if(!b) return;
  logView(isbn);
  const st = stars(b);
  const rc = b.rc>0 ? ` · ${b.rc.toLocaleString()}人评` : "";
  const subcat = b.subcat ? `<span class="t">${subcatIcon(b.subcat)} ${subcatName(b.subcat)}</span>` : "";
  const descBlock = b.desc
    ? `<div class="desc-block"><h4>内容简介</h4><div class="desc-body">${esc(b.desc)}</div></div>`
    : `<div class="desc-block"><div class="desc-body" style="color:var(--sub)">（暂无简介）</div></div>`;
  modal.innerHTML = `
    <div class="modal-head">
      ${coverHtml(b)}
      <div style="flex:1;min-width:0">
        <h2>《${esc(b.title_zh||b.title)}》</h2>
        <div class="meta">作者：${esc(b.author)}</div>
        <div class="meta">${b.year} · ${esc(b.publisher)}</div>
        <div class="tags">${subcat}<span class="t">${esc(b.length||"长篇")}</span></div>
        ${st?`<div class="stars" style="color:#c77e2e;margin-top:6px">${st}${rc}</div>`:""}
      </div>
    </div>
    ${descBlock}
    <button class="modal-close">关 闭</button>`;
  overlay.hidden = false;
}

// ---------- 事件 ----------
let debounce;
searchInput.addEventListener("input", ()=>{
  clearTimeout(debounce);
  debounce = setTimeout(renderAll, 150);
});

main.addEventListener("click", (e)=>{
  const card = e.target.closest(".card");
  if(card) openDetail(card.dataset.isbn);
});

overlay.addEventListener("click", (e)=>{
  if(e.target===overlay || e.target.classList.contains("modal-close")) overlay.hidden = true;
});

// 问卷事件
document.getElementById("ob-body").addEventListener("click", (e)=>{
  const opt = e.target.closest(".ob-opt");
  if(!opt) return;
  const step = OB_STEPS[obStep];
  const v = opt.dataset.v;
  if(step.multi){
    if(!obAnswers[step.key]) obAnswers[step.key] = [];
    const idx = obAnswers[step.key].indexOf(v);
    if(idx>=0) obAnswers[step.key].splice(idx,1);
    else obAnswers[step.key].push(v);
  } else {
    obAnswers[step.key] = v;
  }
  renderObStep();
});

document.getElementById("ob-next").addEventListener("click", ()=>{
  if(obStep < OB_STEPS.length-1){ obStep++; renderObStep(); }
  else finishOnboarding();
});
document.getElementById("ob-back").addEventListener("click", ()=>{
  if(obStep>0){ obStep--; renderObStep(); }
});

document.getElementById("retry-btn").addEventListener("click", showOnboarding);

loadData();
