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
# 佐藤さんが見つけた英数字のIDでOKです。空欄でもBingが動くようにしました。
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

st.set_page_config(page_title="商品画像見えるくん", layout="wide")

# ==========================================
# 🎨 印刷・スマホ・ダークモード用CSS
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
    .product-card { display: flex; flex-direction: column; height: 100%; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #333;
        overflow: hidden; margin-bottom: 8px; height: 260px;
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }
    .product-title { font-weight: 800; font-size: 0.95rem; height: 2.4em; overflow: hidden; color: #fff !important; }
    .product-details { font-size: 0.75rem; color: #ccc !important; }

    @media screen and (max-width: 800px) {
        div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: column !important; }
        .product-card { flex-direction: row !important; align-items: center; }
        .product-image-container { width: 90px !important; height: 90px !important; min-width: 90px; margin-right: 15px; margin-bottom: 0; }
    }

    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], .no-print, .stButton { display: none !important; }
        body, html, .stApp { background-color: white !important; color: black !important; }
        .product-title { color: #000 !important; }
        .product-details { color: #333 !important; }
        /* 🌟 印刷時に画像が薄くなるのを防ぐ */
        .product-image-container img { opacity: 1 !important; visibility: visible !important; display: block !important; filter: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔍 強化版・画像検索エンジン（Bingメイン）
# ==========================================
def fetch_bing_images(query, code):
    """Bingから画像を力技で抜き出す"""
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return []
        
        soup = BeautifulSoup(res.text, 'html.parser')
        urls = []
        
        # 方法1: JSONデータ(iusc)から抜き出す
        for a in soup.find_all('a', class_='iusc'):
            try:
                m = json.loads(a.get('m', '{}'))
                murl = m.get('murl')
                if murl and str(code).lower() in murl.lower():
                    urls.append(murl)
            except: continue
            
        # 方法2: JSONがダメなら直接imgタグを狙う
        if not urls:
            for img in soup.find_all('img', class_='mimg'):
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http'):
                    urls.append(src)
        
        return list(dict.fromkeys(urls))[:5]
    except: return []

def get_rakuten_images_simple(code):
    """楽天API（もしIDが正しければ動く）"""
    if not RAKUTEN_APP_ID or "-" in RAKUTEN_APP_ID: # 英数字ハイフン付きはスキップ
        return []
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 3, "imageFlag": 1}
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            return [it["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0] for it in items if it["Item"].get("mediumImageUrls")]
    except: pass
    return []

def get_best_images(code, name):
    """楽天とBingを合わせて最高の5枚を返す"""
    code_str = str(code).strip().upper()
    r_urls = get_rakuten_images_simple(code_str)
    b_urls = fetch_bing_images(f"adidas {name} {code_str}", code_str)
    
    combined = list(dict.fromkeys(r_urls + b_urls))
    return combined[:5]

# ==========================================
# 🛠️ ツール・データ処理
# ==========================================
def save_data(items):
    with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def guess_column(columns, keywords, default=0):
    for k in keywords:
        for i, c in enumerate(columns):
            if k.lower() in str(c).lower(): return i
    return default

# ==========================================
# メイン画面
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
    st.header("⚙️ 管理メニュー")
    is_print_mode = st.toggle("コンパクト表示（印刷用）")
    if st.button("🖨️ 今すぐ印刷", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)
    st.write("---")
    if st.button("🗑️ データをリセット"):
        st.session_state.catalog_items = []
        st.session_state.generated = False
        if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
        st.rerun()

# --- ファイル読み込み ---
if not st.session_state.generated:
    up = st.file_uploader("Excelファイルをアップロード", type=['xlsx', 'csv'])
    if up:
        df = pd.read_excel(up, header=None) if up.name.endswith('xlsx') else pd.read_csv(up, header=None)
        # ヘッダー位置を推測
        h_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() and str(v).lower() != 'nan') >= 3:
                h_idx = i; break
        df.columns = [str(c).strip() if str(c).strip() else f"列{i+1}" for i, c in enumerate(df.iloc[h_idx])]
        df = df.iloc[h_idx+1:].reset_index(drop=True)
        cols = df.columns.tolist()

        with st.expander("📊 列の割り当て確認", expanded=True):
            c1, c2, c3 = st.columns(3)
            col_art = c1.selectbox("品番(Article)", cols, index=guess_column(cols, ['art', '品番', 'code']))
            col_name = c2.selectbox("商品名(Name)", cols, index=guess_column(cols, ['name', '名称', '商品名']))
            # 🌟 佐藤さんリクエスト：デフォルトを「列12」にする（存在する場合）
            col_stat = c3.selectbox("状態(Status)", ["(なし)"] + cols, index=cols.index("列12")+1 if "列12" in cols else 0)
            col_qty = c1.selectbox("数量(Qty)", ["(なし)"] + cols, index=guess_column(cols, ['qty', '数量'])+1)

        if st.button("カタログを作成する", type="primary", use_container_width=True):
            data = df[df[col_art].astype(str).strip() != ""].drop_duplicates(subset=[col_art])
            st.info(f"画像を検索しています... ({len(data)}件)")
            p = st.progress(0)
            items = []
            
            # 高速化のために並列で検索
            def process(args):
                i, row = args
                art, name = str(row[col_art]).strip(), str(row[col_name]).strip()
                urls = get_best_images(art, name)
                return i, {"art": art, "name": name, "status": str(row.get(col_stat, "")), "qty": str(row.get(col_qty, "0")), "url": urls[0] if urls else None}

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
                futures = [exe.submit(process, (i, r)) for i, (_, r) in enumerate(data.iterrows())]
                for i, f in enumerate(concurrent.futures.as_completed(futures)):
                    items.append(f.result())
                    p.progress((i + 1) / len(data))
            
            items.sort(key=lambda x: x[0])
            st.session_state.catalog_items = [it[1] for it in items]
            st.session_state.generated = True
            save_data(st.session_state.catalog_items)
            st.rerun()

# --- カタログ表示 ---
if st.session_state.generated:
    it = st.session_state.catalog_items
    n = 5 if is_print_mode else 3
    for i in range(0, len(it), n):
        row_cols = st.columns(n)
        for j, item in enumerate(it[i:i+n]):
            with row_cols[j]:
                u = item.get("url")
                img = f'<img src="{u}" loading="eager">' if u else '<div style="color:#666; padding:20px;">画像なし</div>'
                card = f"""
                <div class="product-card">
                    <div class="product-image-container">{img}</div>
                    <div class="product-info">
                        <div class="product-title">{item['name']}</div>
                        <div class="product-details">Art: {item['art']} | Qty: {item['qty']}<br>Status: {item['status']}</div>
                    </div>
                </div>
                """
                st.markdown(card, unsafe_allow_html=True)
