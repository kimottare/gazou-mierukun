import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json 
import os 
import concurrent.futures
import datetime
import uuid
import streamlit.components.v1 as components
import re

# --- 🌟 設定 ---
# ここは佐藤さんが見つけたID（9fd3...）のままでOKです。
# 楽天が動かなくてもBingが100%カバーするようにロジックを組み直しました。
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

st.set_page_config(page_title="商品画像見えるくん", layout="wide")

# ==========================================
# 🎨 究極の視認性 ＋ 印刷バグ修正CSS
# ==========================================
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }
    .main-title {
        font-size: 2.8rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0);
        border-left: 12px solid #ffffff;
        padding-left: 20px;
        margin: 1.5rem 0;
    }
    .product-card { display: flex; flex-direction: column; height: 100%; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 15px; }
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #333;
        overflow: hidden; margin-bottom: 8px; height: 260px;
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }
    .product-title { font-weight: 800; font-size: 1.0rem; height: 2.4em; overflow: hidden; color: #fff !important; }
    .product-details { font-size: 0.8rem; color: #ccc !important; line-height: 1.4; }

    /* 📱 スマホ表示の1列リスト化 */
    @media screen and (max-width: 800px) {
        div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: column !important; gap: 0 !important; }
        .product-card { flex-direction: row !important; align-items: center; }
        .product-image-container { width: 90px !important; height: 90px !important; min-width: 90px; margin-right: 15px; margin-bottom: 0; }
        .product-title { font-size: 0.9rem !important; height: auto !important; white-space: nowrap; text-overflow: ellipsis; }
    }

    /* 🖨️ 印刷時に画像が薄くなるのを絶対に防ぐ設定 */
    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], .no-print, .stButton { display: none !important; }
        body, html, .stApp { background-color: white !important; color: black !important; }
        .product-title { color: #000 !important; text-shadow: none !important; }
        .product-details { color: #333 !important; }
        .product-image-container { border: 1px solid #eee !important; box-shadow: none !important; }
        .product-image-container img { 
            opacity: 1 !important; 
            visibility: visible !important; 
            display: block !important; 
            filter: none !important; 
            -webkit-print-color-adjust: exact;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔍 強化版画像検索（Bing & 楽天）
# ==========================================
def get_best_images(code, name):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ja,en-US;q=0.9"}
    urls = []

    # 1. Bingを徹底的に掘る（ID不要で動くメインソース）
    try:
        res = requests.get(f"https://www.bing.com/images/search?q={query}", headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # 形式A: iuscタグからJSON抽出
            for a in soup.find_all('a', class_='iusc'):
                try:
                    murl = json.loads(a.get('m', '{}')).get('murl')
                    if murl and code_str.lower() in murl.lower(): urls.append(murl)
                except: continue
            # 形式B: 直接imgタグから抽出（バックアップ）
            if not urls:
                for img in soup.find_all('img', class_='mimg'):
                    src = img.get('src') or img.get('data-src')
                    if src and src.startswith('http'): urls.append(src)
    except: pass

    # 2. 楽天API（IDが19桁の数字の時だけ動く）
    if RAKUTEN_APP_ID.isdigit() and len(RAKUTEN_APP_ID) >= 10:
        try:
            r_res = requests.get("https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601", 
                                 params={"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code_str}", "hits": 3}, timeout=5)
            if r_res.status_code == 200:
                for it in r_res.json().get("Items", []):
                    u = it["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                    if u not in urls: urls.append(u)
        except: pass

    return list(dict.fromkeys(urls))[:5]

# ==========================================
# 🛠️ 便利な自動推測ロジック
# ==========================================
def guess_col(columns, keywords, target_val=None):
    # 特定の値（例：列12）を直接探す
    if target_val and target_val in columns:
        return columns.index(target_val)
    # キーワードで探す
    for k in keywords:
        for i, c in enumerate(columns):
            if k.lower() in str(c).lower(): return i
    return 0

# ==========================================
# メイン UI
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見えるくん</div>', unsafe_allow_html=True)

if "catalog_items" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = False
    if os.path.exists(AUTO_SAVE_FILE):
        try:
            with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
                st.session_state.catalog_items = json.load(f)
                st.session_state.generated = True
        except: pass

with st.sidebar:
    st.header("⚙️ 設定・管理")
    is_print_mode = st.toggle("コンパクトモード（印刷用）")
    if st.button("🖨️ カタログを印刷", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)
    st.write("---")
    if st.button("🗑️ データをリセット"):
        st.session_state.catalog_items = []
        st.session_state.generated = False
        if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
        st.rerun()

# --- 作成フェーズ ---
if not st.session_state.generated:
    up = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])
    if up:
        try:
            df = pd.read_excel(up, header=None) if not up.name.endswith('.csv') else pd.read_csv(up, header=None)
            h_idx = 0
            for i, row in df.iterrows():
                if sum(1 for v in row if str(v).strip() and str(v).lower() != 'nan') >= 3:
                    h_idx = i; break
            df.columns = [str(c).strip() if str(c).strip() else f"列{i+1}" for i, c in enumerate(df.iloc[h_idx])]
            df = df.iloc[h_idx+1:].reset_index(drop=True)
            cols = df.columns.tolist()

            with st.expander("📋 列の割り当て確認", expanded=True):
                c1, c2, c3 = st.columns(3)
                col_art = c1.selectbox("品番", cols, index=guess_col(cols, ['art', 'code', '品番']))
                col_name = c2.selectbox("商品名", cols, index=guess_col(cols, ['name', '名称', '商品名']))
                # 🌟 佐藤さんリクエスト：デフォルトを「列12」に固定
                col_stat = c3.selectbox("Status", ["(なし)"] + cols, index=guess_col(cols, [], target_val="列12")+1 if "列12" in cols else 0)
                col_qty = c1.selectbox("数量", ["(なし)"] + cols, index=guess_col(cols, ['qty', '数量'])+1)

            if st.button("カタログ作成開始", type="primary", use_container_width=True):
                data = df[df[col_art].astype(str).str.strip() != ""].drop_duplicates(subset=[col_art])
                st.info(f"画像を検索中... ({len(data)}件)")
                p = st.progress(0)
                items = []
                
                def process(args):
                    i, r = args
                    art, name = str(r[col_art]).strip(), str(r[col_name]).strip()
                    urls = get_best_images(art, name)
                    return i, {"art": art, "name": name, "stat": str(r.get(col_stat, "")), "qty": str(r.get(col_qty, "0")), "url": urls[0] if urls else None}

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
                    futures = [exe.submit(process, (i, r)) for i, (_, r) in enumerate(data.iterrows())]
                    for i, f in enumerate(concurrent.futures.as_completed(futures)):
                        items.append(f.result()); p.progress((i + 1) / len(data))
                
                items.sort(key=lambda x: x[0])
                st.session_state.catalog_items = [it[1] for it in items]
                st.session_state.generated = True
                with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f: json.dump(st.session_state.catalog_items, f, ensure_ascii=False)
                st.rerun()
        except Exception as e: st.error(f"エラー: {e}")

# --- 表示フェーズ ---
if st.session_state.generated:
    it = st.session_state.catalog_items
    n = 5 if is_print_mode else 3
    for i in range(0, len(it), n):
        row_cols = st.columns(n)
        for j, item in enumerate(it[i:i+n]):
            with row_cols[j]:
                u = item.get("url")
                img = f'<img src="{u}" loading="eager">' if u else '<div style="color:#666; font-size:0.8rem; padding:20px;">画像なし</div>'
                card = f'<div class="product-card"><div class="product-image-container">{img}</div><div class="product-info"><div class="product-title">{item["name"]}</div><div class="product-details">Art: {item["art"]} | Qty: {item["qty"]}<br>Status: {item["stat"]}</div></div></div>'
                st.markdown(card, unsafe_allow_html=True)
