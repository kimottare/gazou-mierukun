import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json 
import os 
import concurrent.futures
import datetime
import socket 
import uuid
import streamlit.components.v1 as components

# --- 🌟 設定 ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

@st.cache_resource
def get_shared_store():
    return {}

st.set_page_config(page_title="商品画像見える君", layout="wide")

# ==========================================
# 🎨 究極の視認性・モバイル2列・印刷最適化CSS
# ==========================================
st.markdown("""
    <style>
    /* --- 画面表示用 --- */
    .main-title {
        font-size: 2.8rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        margin-top: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        text-align: left;
        border-left: 12px solid #ffffff;
        padding-left: 20px;
    }
    .product-title {
        font-weight: 800; font-size: 1.0rem; line-height: 1.2; height: 2.4em;
        overflow: hidden; margin-bottom: 4px; color: #ffffff !important;
        text-shadow: 2px 2px 5px rgba(0,0,0,1.0) !important;
    }
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #333;
        overflow: hidden; margin-bottom: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.6);
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }
    .product-details {
        font-size: 0.75rem; color: #e0e0e0 !important; line-height: 1.3;
        height: 3.9em; overflow: hidden; margin-bottom: 8px;
        text-shadow: 1px 1px 3px rgba(0,0,0,1.0);
    }
    footer {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stHeader"] { background: transparent !important; }

    /* 📱 モバイル2列強制（iPhone Edge/Safari対応） */
    @media screen and (max-width: 800px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important; flex-direction: row !important;
            flex-wrap: wrap !important; width: 100% !important; gap: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: 50% !important; flex: 0 0 50% !important;
            min-width: 50% !important; max-width: 50% !important; padding: 8px !important;
        }
        .product-image-container { height: 150px !important; }
        .main-title { font-size: 1.6rem !important; }
    }

    /* 🖨️ 印刷用設定（背景白・文字黒・影なし） */
    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, [data-testid="stExpander"],
        [data-testid="stMultiSelect"], [data-testid="stCheckbox"], 
        .no-print, iframe, .stTextInput, .stAlert, hr { display: none !important; }
        body, .main, [data-testid="stAppViewContainer"] { background-color: white !important; color: black !important; }
        .main-title { color: #000 !important; text-shadow: none !important; border-left: 8px solid #000 !important; }
        .product-title { color: #000 !important; text-shadow: none !important; }
        .product-details { color: #333 !important; text-shadow: none !important; }
        .product-image-container { border: 1px solid #ddd !important; box-shadow: none !important; background: #fff !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 ロジック補助 ---
def guess_column_index(columns, keywords, default_idx=0, exclude=[]):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            c_low = str(col).lower()
            if keyword.lower() in c_low and not any(ex.lower() in c_low for ex in exclude):
                return idx
    return default_idx

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
        res = requests.get(url, params={"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code_str}", "hits": 1}, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            if items: return {"url": items[0]["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]}
    except: pass
    return None

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass 

# ==========================================
# UI
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

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
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.button("🖨️ カタログを印刷", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)

    if st.session_state.generated:
        st.write("---")
        st.subheader("🎯 絞り込み")
        is_new_only = st.checkbox("✨ 新規入荷のみ", key="new_only_toggle")
        items = st.session_state.catalog_items
        unique_bs = sorted(list(set([str(i["bs"]).strip() for i in items if i.get("bs") and not any(c.isdigit() for c in str(i["bs"])) and len(str(i["bs"])) > 2])))
        
        sel_bs = []
        if unique_bs:
            with st.container(height=200):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}", value=st.session_state.get(f"chk_{b}", True)):
                        sel_bs.append(b)
        
        if st.button("🗑️ リセット", type="secondary", use_container_width=True):
            if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
            st.session_state.catalog_items = []
            st.session_state.generated = False
            st.rerun()

if not st.session_state.generated:
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'csv'])
    if uploaded_file:
        df = pd.read_excel(uploaded_file, header=None) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file, header=None)
        h_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() != "") >= 3: h_idx = i; break
        df.columns = df.iloc[h_idx]; df = df.iloc[h_idx+1:].reset_index(drop=True)
        cols = [str(c).strip() for c in df.columns]

        with st.expander("📋 列割り当て確認", expanded=True):
            c1, c2, c3 = st.columns(3)
            art_c = c1.selectbox("Article", cols, index=guess_column_index(cols, ['art', 'code']))
            name_c = c2.selectbox("Name", cols, index=guess_column_index(cols, ['名称', 'name']))
            bs_c = c3.selectbox("BS (カテゴリー)", cols, index=guess_column_index(cols, ['BS'], exclude=['size', 'サイズ']))
            size_c = c1.selectbox("Size", cols, index=guess_column_index(cols, ['size', 'サイズ']))
            qty_c = c2.selectbox("Qty", cols, index=guess_column_index(cols, ['qty', '数量']))
            status_c = c3.selectbox("Status", cols, index=min(11, len(cols)-1))

        if st.button("カタログ作成開始", type="primary", use_container_width=True):
            results = []
            progress = st.progress(0)
            target_df = df[df[art_c].notnull()].drop_duplicates(subset=[art_c])
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                futures = {exe.submit(get_best_image, row[art_c], row[name_c]): row for _, row in target_df.iterrows()}
                for i, f in enumerate(concurrent.futures.as_completed(futures)):
                    row, img = futures[f], f.result()
                    results.append({
                        "code": str(row[art_c]).strip(), "name": str(row[name_c]).strip(),
                        "bs": str(row[bs_c]).strip(), "size": str(row[size_c]).strip(),
                        "qty": str(row[qty_c]).strip(), "status": str(row[status_c]).strip(),
                        "auto_url": img["url"] if img else "", "manual_url": ""
                    })
                    progress.progress((i + 1) / len(target_df))
            st.session_state.catalog_items = results
            st.session_state.generated = True
            save_auto_save_data(results)
            st.rerun()

# --- 📊 表示エリア（機能復旧） ---
if st.session_state.generated:
    display = [i for i in st.session_state.catalog_items if i.get("bs") in sel_bs]
    if is_new_only:
        display = [i for i in display if str(i.get("status", "")).upper() in ["#N/A", "#REF!", "NAN", "", "NEW"]]

    # 🌟 合計件数と点数の計算・表示を復旧
    total_q = sum([float(i.get("qty", 0)) if str(i.get("qty", "0")).replace('.','',1).isdigit() else 0 for i in display])
    st.info(f"📊 **{len(display)}** 品番 / 合計 **{int(total_q)}** 点 を表示中")

    n_cols = 5 if is_print_mode else 2
    img_h = "140px" if is_print_mode else "240px"
    for i in range(0, len(display), n_cols):
        cols = st.columns(n_cols) 
        for j, item in enumerate(display[i:i+n_cols]):
            with cols[j]:
                st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item["qty"]} / {item["status"]}</div>', unsafe_allow_html=True)
                img = item["manual_url"] or item["auto_url"]
                if img: st.markdown(f'<div class="product-image-container" style="height:{img_h};"><img src="{img}"></div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="product-image-container" style="height:{img_h}; background:#f8f9fa;"><div style="color:#999; font-size:0.8rem;">画像なし</div></div>', unsafe_allow_html=True)
                
                if not is_print_mode:
                    new_u = st.text_input("URL貼付", value=item["manual_url"], key=f"inp_{item['code']}")
                    if new_u != item["manual_url"]:
                        item["manual_url"] = new_u
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
