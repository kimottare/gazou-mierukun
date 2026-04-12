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

# --- 🌟 基本設定 ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

@st.cache_resource
def get_shared_store():
    return {}

st.set_page_config(page_title="商品画像見える君", layout="wide")

# ==========================================
# 🎨 究極の視認性・モバイル2列「絶対固定」CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: #0e1117;
    }

    .main-title {
        font-size: 2.5rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        border-left: 12px solid #ffffff;
        padding-left: 20px;
        margin: 1.5rem 0 !important;
    }

    .product-title {
        font-weight: 800;
        font-size: 1.0rem;
        line-height: 1.2;
        height: 2.4em;
        overflow: hidden;
        color: #ffffff !important;
        text-shadow: 2px 2px 8px rgba(0,0,0,1.0) !important;
        margin-bottom: 4px;
    }

    .product-image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        background: #ffffff;
        border-radius: 10px;
        border: 1px solid #333;
        overflow: hidden;
        margin-bottom: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.6);
    }

    .product-image-container img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
    }

    .product-details {
        font-size: 0.75rem;
        color: #e0e0e0 !important;
        line-height: 1.3;
        height: 4.2em;
        overflow: hidden;
        text-shadow: 1px 1px 4px rgba(0,0,0,1.0);
        margin-bottom: 10px;
    }

    footer {visibility: hidden;}
    [data-testid="stHeader"] { background: transparent !important; }

    /* 📱 モバイル2列強制命令 */
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
            padding: 8px !important;
        }
        .product-image-container { height: 160px !important; }
        .main-title { font-size: 1.6rem !important; border-left-width: 8px; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 検索・ロジック ---

def scrape_bing_high_res_image(query, code):
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m_str = a.get('m')
            if m_str:
                murl = json.loads(m_str).get('murl')
                if murl and str(code).strip().lower() in murl.lower():
                    return murl, True
    except: pass
    return None, False

def get_rakuten_image(code):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 3}
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                img_url = item["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                return img_url, True
    except: pass
    return None, False

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    rak_url, rak_exact = get_rakuten_image(code_str)
    if rak_exact: return {"url": rak_url, "source": "楽天"}
    bing_url, bing_exact = scrape_bing_high_res_image(f"adidas {name} {code_str}", code_str)
    if bing_exact: return {"url": bing_url, "source": "Bing"}
    return None

def guess_column_index(columns, targets, excludes=['size', 'サイズ']):
    for target in targets:
        for idx, col in enumerate(columns):
            c_low = str(col).lower()
            if target in c_low and not any(ex in c_low for ex in excludes):
                return idx
    return 0

def save_auto_save_data(items):
    with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

@st.dialog("データの全消去")
def confirm_reset():
    st.warning("全データを削除します。よろしいですか？")
    if st.button("はい、削除します"):
        st.session_state.generated = False
        if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
        st.rerun()

# ==========================================
# メイン UI
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

if "generated" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = os.path.exists(AUTO_SAVE_FILE)
    if st.session_state.generated:
        with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state.catalog_items = json.load(f)

# --- サイドバー (絞り込み) ---
with st.sidebar:
    st.header("⚙️ 管理")
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.session_state.generated:
        st.write("---")
        st.subheader("🎯 絞り込み")
        # ✨ 新規入荷フィルタを最上部に配置
        is_new_only = st.checkbox("✨ 新規入荷のみ (#N/A)", value=False)
        
        items = st.session_state.catalog_items
        unique_bs = sorted(list(set([str(i.get("bs", "")).strip() for i in items if str(i.get("bs", "")).strip()])))
        
        sel_bs = []
        if unique_bs:
            c1, c2 = st.columns(2)
            if c1.button("全選択"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = True
            if c2.button("全解除"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = False
            
            with st.container(height=250):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}", value=st.session_state.get(f"chk_{b}", True)):
                        sel_bs.append(b)
        
        if st.button("🗑️ データをクリア"): confirm_reset()

# --- メインロジック ---
if not st.session_state.generated:
    uploaded_file = st.file_uploader("Excel/CSVアップロード", type=['xlsx', 'csv'])
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None)
        else:
            df = pd.read_excel(uploaded_file, na_filter=False, dtype=str, header=None)
        
        header_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() != "") >= 3:
                header_idx = i
                break
        df.columns = df.iloc[header_idx].tolist()
        df = df.iloc[header_idx+1:].reset_index(drop=True)
        cols = [str(c).strip() for c in df.columns]

        with st.expander("📋 列割り当て", expanded=True):
            c1, c2, c3 = st.columns(3)
            code_col = c1.selectbox("Article", cols, index=guess_column_index(cols, ['art', 'code']))
            size_col = c1.selectbox("Size", cols, index=guess_column_index(cols, ['size', 'サイズ'], excludes=[]))
            name_col = c2.selectbox("Name", cols, index=guess_column_index(cols, ['名称', 'name']))
            qty_col = c2.selectbox("Qty", cols, index=guess_column_index(cols, ['qty', '数量']))
            # カテゴリ(BS)とステータス(新規判定用)
            bs_col = c3.selectbox("BS (カテゴリー)", cols, index=guess_column_index(cols, ['bs', 'category', '部門']))
            status_col = c3.selectbox("Status (新規入荷判定用)", cols, index=guess_column_index(cols, ['status', '状況', '状態', '新']))

        if st.button("作成開始", type="primary", use_container_width=True):
            display_df = df[df[code_col].astype(str).str.strip() != ""].drop_duplicates(subset=[code_col])
            results = []
            p_bar = st.progress(0)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                futures = []
                for _, row in display_df.iterrows():
                    code = str(row[code_col]).strip()
                    name = str(row[name_col]).strip()
                    futures.append(exe.submit(get_best_image, code, name))
                
                for i, f in enumerate(futures):
                    img = f.result()
                    row = display_df.iloc[i]
                    results.append({
                        "code": str(row[code_col]).strip(),
                        "name": str(row[name_col]).strip(),
                        "bs": str(row[bs_col]).strip(),
                        "size": str(row[size_col]).strip(),
                        "qty": str(row[qty_col]).strip(),
                        "status": str(row[status_col]).strip(),
                        "auto_url": img["url"] if img else None,
                        "manual_url": ""
                    })
                    p_bar.progress((i + 1) / len(display_df))
            
            st.session_state.catalog_items = results
            st.session_state.generated = True
            save_auto_save_data(results)
            st.rerun()

# --- 表示エリア ---
if st.session_state.generated:
    items = st.session_state.catalog_items
    
    # 🎯 フィルタリングロジックの完全修復
    filtered = items
    if sel_bs:
        filtered = [i for i in filtered if i.get("bs") in sel_bs]
    if is_new_only:
        # #N/A, #REF!, 空白などを新規として判定
        filtered = [i for i in filtered if str(i.get("status", "")).upper() in ["#N/A", "#REF!", "NAN", "", "NEW"]]

    st.info(f"📊 {len(filtered)} 品番を表示中")
    
    # QR / 保存ボタン
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        sid = st.session_state.get("share_id", uuid.uuid4().hex[:8])
        get_shared_store()[sid] = filtered
        qr_html = f'<div style="text-align:center;"><div id="qrcode" style="display:inline-block;background:white;padding:5px;"></div></div><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><script>new QRCode(document.getElementById("qrcode"), {{text:window.parent.location.href.split("?")[0]+"?sid={sid}", width:100, height:100}});</script>'
        components.html(qr_html, height=120)

    num_cols = 5 if is_print_mode else 2
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols)
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item["qty"]}点 / {item["status"]}</div>', unsafe_allow_html=True)
                
                url = item.get("manual_url") or item.get("auto_url")
                if url:
                    st.markdown(f'<div class="product-image-container"><img src="{url}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="product-image-container" style="background:#222;height:160px;"><div style="color:#666;font-size:0.7rem;">NO IMAGE</div></div>', unsafe_allow_html=True)
                
                if not is_print_mode:
                    new_u = st.text_input("URL貼付", value=item.get("manual_url", ""), key=f"url_{item['code']}")
                    if new_u != item.get("manual_url"):
                        item["manual_url"] = new_u
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
