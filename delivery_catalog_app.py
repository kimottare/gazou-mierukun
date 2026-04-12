import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json 
import os 
import concurrent.futures
import uuid
import streamlit.components.v1 as components

# --- ⚙️ 基本設定 ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

st.set_page_config(page_title="商品画像見える君", layout="wide")

# ==========================================
# 🎨 究極の視認性・モバイル2列「鉄壁」CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif; background-color: #0e1117; }

    .main-title {
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        border-left: 12px solid #ffffff;
        padding-left: 15px;
        margin: 1rem 0 !important;
    }

    .product-title {
        font-weight: 800; font-size: 0.95rem; line-height: 1.2; height: 2.4em;
        overflow: hidden; color: #ffffff !important;
        text-shadow: 2px 2px 8px rgba(0,0,0,1.0) !important;
        margin-bottom: 4px;
    }

    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #444;
        overflow: hidden; margin-bottom: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.6);
        height: 240px; 
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }

    .product-details {
        font-size: 0.72rem; color: #efefef !important; line-height: 1.3;
        height: 4.2em; overflow: hidden; text-shadow: 1px 1px 4px rgba(0,0,0,1.0);
    }

    /* 📱 モバイル2列強制命令（iPhone Safari/Edge用） */
    @media screen and (max-width: 800px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: 50% !important;
            flex: 0 0 50% !important;
            min-width: 50% !important;
            max-width: 50% !important;
            padding: 5px !important;
        }
        .product-image-container { height: 155px !important; }
        .main-title { font-size: 1.4rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 検索ロジック ---
def get_best_image(code, name):
    code_str = str(code).strip().upper()
    # 1. 楽天
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
        res = requests.get(url, params={"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code_str}", "hits": 1}, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            if items: return items[0]["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
    except: pass
    # 2. Bing
    try:
        query = f"adidas {name} {code_str}"
        res = requests.get(f"https://www.bing.com/images/search?q={query}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m = json.loads(a.get('m')).get('murl')
            if m and code_str.lower() in m.lower(): return m
    except: pass
    return ""

def save_data(items):
    with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# --- UI ---
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

if "items" not in st.session_state:
    st.session_state.items = []
    if os.path.exists(AUTO_SAVE_FILE):
        with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state.items = json.load(f)

with st.sidebar:
    st.header("⚙️ 設定")
    concurrency = st.slider("⚡ 検索速度", 1, 10, 5)
    is_print = st.toggle("コンパクトモード")
    
    if st.session_state.items:
        st.write("---")
        st.subheader("🎯 絞り込み")
        is_new = st.checkbox("✨ 新規入荷のみ (#N/A)", value=False)
        
        # BS(カテゴリー)からサイズを排除
        all_bs = sorted(list(set([str(i.get("bs", "")).strip() for i in st.session_state.items if i.get("bs") and not any(x in str(i.get("bs")).lower() for x in ['size', '.', '2'])])))
        
        sel_bs = []
        if all_bs:
            with st.container(height=300):
                for b in all_bs:
                    if st.checkbox(b, key=f"c_{b}", value=True): sel_bs.append(b)
        
        if st.button("🗑️ データをクリア"):
            if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
            st.session_state.items = []
            st.rerun()

# --- アップロード & 作成 ---
if not st.session_state.items:
    file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'csv'])
    if file:
        df = pd.read_excel(file, header=None) if file.name.endswith('.xlsx') else pd.read_csv(file, header=None)
        h_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() != "") >= 3: h_idx = i; break
        df.columns = df.iloc[h_idx]; df = df.iloc[h_idx+1:].reset_index(drop=True)
        cols = [str(c).strip() for c in df.columns]

        with st.expander("📋 列の紐付け（重要）", expanded=True):
            c1, c2 = st.columns(2)
            art_c = c1.selectbox("品番", cols, index=0)
            # 🌟 商品名称：個人情報を一切介在させず、列名を直接参照
            name_c = c1.selectbox("商品名称", cols, index=1)
            bs_c = c2.selectbox("BS (カテゴリー)", cols, index=2)
            # 🌟 ステータス：列12 (インデックス11) をデフォルトに
            status_c = c2.selectbox("Status (列12を参照)", cols, index=min(11, len(cols)-1))
            size_c = c1.selectbox("Size", cols, index=min(5, len(cols)-1))
            qty_c = c2.selectbox("Qty", cols, index=min(6, len(cols)-1))

        if st.button("カタログ作成", type="primary", use_container_width=True):
            results = []
            p = st.progress(0)
            target = df[df[art_c].notnull()].drop_duplicates(subset=[art_c])
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                # 🌟 ここで row[name_c] を確実に取得
                future_to_row = {exe.submit(get_best_image, row[art_c], row[name_c]): row for _, row in target.iterrows()}
                for i, future in enumerate(concurrent.futures.as_completed(future_to_row)):
                    row = future_to_row[future]
                    img_url = future.result()
                    results.append({
                        "code": str(row[art_c]).strip(),
                        "name": str(row[name_c]).strip(),
                        "bs": str(row[bs_c]).strip(),
                        "size": str(row[size_c]).strip(),
                        "qty": str(row[qty_c]).strip(),
                        "status": str(row[status_c]).strip(),
                        "url": img_url, "manual": ""
                    })
                    p.progress((i + 1) / len(target))
            
            st.session_state.items = results
            save_data(results)
            st.rerun()

# --- 表示エリア ---
if st.session_state.items:
    display = [i for i in st.session_state.items if i.get("bs") in sel_bs]
    if is_new:
        display = [i for i in display if str(i.get("status", "")).upper() in ["#N/A", "#REF!", "NAN", "", "NEW"]]

    # カタログ表示
    n_cols = 5 if is_print else 2
    for i in range(0, len(display), n_cols):
        cols = st.columns(n_cols)
        for j, item in enumerate(display[i:i+n_cols]):
            with cols[j]:
                # 🌟 正確な名称を表示
                st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item["qty"]} / {item["status"]}</div>', unsafe_allow_html=True)
                img = item["manual"] if item["manual"] else item["url"]
                if img:
                    st.markdown(f'<div class="product-image-container"><img src="{img}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="product-image-container" style="background:#222;"><div style="color:#666;">NO IMAGE</div></div>', unsafe_allow_html=True)
                
                if not is_print:
                    new_m = st.text_input("URL", value=item["manual"], key=f"m_{item['code']}")
                    if new_m != item["manual"]:
                        item["manual"] = new_m
                        save_data(st.session_state.items)
                        st.rerun()
