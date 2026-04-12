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

    /* タイトル：白文字＋強力シャドウ */
    .main-title {
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        border-left: 12px solid #ffffff;
        padding-left: 15px;
        margin: 1rem 0 !important;
    }

    /* 商品名：視認性重視 */
    .product-title {
        font-weight: 800; font-size: 0.95rem; line-height: 1.2; height: 2.4em;
        overflow: hidden; color: #ffffff !important;
        text-shadow: 2px 2px 8px rgba(0,0,0,1.0) !important;
        margin-bottom: 4px;
    }

    /* 画像コンテナ：スマホ2列時の高さを死守 */
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #444;
        overflow: hidden; margin-bottom: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.6);
        height: 240px; /* デフォルト */
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }

    /* 詳細テキスト */
    .product-details {
        font-size: 0.72rem; color: #efefef !important; line-height: 1.3;
        height: 4.2em; overflow: hidden; text-shadow: 1px 1px 4px rgba(0,0,0,1.0);
    }

    /* 📱 iPhone Safari/Edge 対策：2列強制（!important多用） */
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
        .main-title { font-size: 1.4rem !important; border-left-width: 8px; }
        .product-title { font-size: 0.8rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 検索・ロジック ---
def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    # 楽天
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
        res = requests.get(url, params={"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code_str}", "hits": 1}, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            if items: return {"url": items[0]["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0], "source": "楽天"}
    except: pass
    # Bing
    try:
        query = f"adidas {name} {code_str}"
        res = requests.get(f"https://www.bing.com/images/search?q={query}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m = json.loads(a.get('m')).get('murl')
            if m and code_str.lower() in m.lower(): return {"url": m, "source": "Bing"}
    except: pass
    return None

def save_auto_save_data(items):
    with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ==========================================
# メイン UI
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

if "catalog_items" not in st.session_state:
    st.session_state.catalog_items = []
    if os.path.exists(AUTO_SAVE_FILE):
        with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state.catalog_items = json.load(f)

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定")
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.session_state.catalog_items:
        st.write("---")
        st.subheader("🎯 絞り込み")
        # 🌟 復活：新規入荷フィルタ（Status列に基づく）
        is_new_only = st.checkbox("✨ 新規入荷のみ (#N/A)", value=False)
        
        # BS（カテゴリー）抽出：サイズ列の混入を徹底排除
        items = st.session_state.catalog_items
        unique_bs = sorted(list(set([str(i.get("bs", "")).strip() for i in items if i.get("bs") and not any(x in str(i.get("bs")).lower() for x in ['size', '2', '24', '25', '26', '27'])])))
        
        sel_bs = []
        if unique_bs:
            col_a, col_b = st.columns(2)
            if col_a.button("全選択"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = True
            if col_b.button("全解除"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = False
            
            with st.container(height=300):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}", value=st.session_state.get(f"chk_{b}", True)):
                        sel_bs.append(b)
        
        if st.button("🗑️ データを全消去"):
            if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
            st.session_state.catalog_items = []
            st.rerun()

# --- アップロード画面 ---
if not st.session_state.catalog_items:
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'csv'])
    if uploaded_file:
        df = pd.read_excel(uploaded_file, header=None) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file, header=None)
        
        # ヘッダー自動検知
        h_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() != "") >= 3:
                h_idx = i; break
        df.columns = df.iloc[h_idx]; df = df.iloc[h_idx+1:].reset_index(drop=True)
        cols = [str(c).strip() for c in df.columns]

        with st.expander("📋 列の紐付け設定", expanded=True):
            c1, c2 = st.columns(2)
            art_c = c1.selectbox("Article (品番)", cols, index=0)
            name_c = c1.selectbox("Name (商品名)", cols, index=1)
            bs_c = c2.selectbox("BS (カテゴリー)", cols, index=2)
            # 🌟 10列12番付近のステータス列を自動指定（なければ選択）
            status_c = c2.selectbox("Status (新規入荷判定用)", cols, index=min(10, len(cols)-1))
            size_c = c1.selectbox("Size (サイズ)", cols, index=min(5, len(cols)-1))
            qty_c = c2.selectbox("Qty (在庫数)", cols, index=min(6, len(cols)-1))

        if st.button("カタログ作成開始", type="primary", use_container_width=True):
            results = []
            progress = st.progress(0)
            target_df = df[df[art_c].notnull()].drop_duplicates(subset=[art_c])
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                future_to_code = {exe.submit(get_best_image, row[art_c], row[name_c]): row for _, row in target_df.iterrows()}
                for i, future in enumerate(concurrent.futures.as_completed(future_to_code)):
                    row = future_to_code[future]
                    img = future.result()
                    results.append({
                        "code": str(row[art_c]).strip(), "name": str(row[name_c]).strip(),
                        "bs": str(row[bs_c]).strip(), "size": str(row[size_c]).strip(),
                        "qty": str(row[qty_c]).strip(), "status": str(row[status_c]).strip(),
                        "auto_url": img["url"] if img else "", "manual_url": ""
                    })
                    progress.progress((i + 1) / len(target_df))
            
            st.session_state.catalog_items = results
            save_auto_save_data(results)
            st.rerun()

# --- 表示エリア ---
if st.session_state.catalog_items:
    # フィルタリング：BSと新規入荷のAND条件
    display_items = [i for i in st.session_state.catalog_items if i.get("bs") in sel_bs]
    if is_new_only:
        # 佐藤さんの「10列目」仕様：#N/A、空、またはNEWという文字列を新規とみなす
        display_items = [i for i in display_items if str(i.get("status", "")).upper() in ["#N/A", "#REF!", "NAN", "", "NEW"]]

    # 📱 スマホ転送用QR
    if not is_print_mode:
        sid = uuid.uuid4().hex[:8]
        qr_html = f'<div style="text-align:center;"><div id="qrcode" style="display:inline-block;background:white;padding:5px;border-radius:4px;"></div></div><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><script>new QRCode(document.getElementById("qrcode"), {{text:window.parent.location.href.split("?")[0]+"?sid={sid}", width:90, height:90}});</script>'
        components.html(qr_html, height=110)

    # カタログレンダリング
    n_cols = 5 if is_print_mode else 2
    for i in range(0, len(display_items), n_cols):
        cols = st.columns(n_cols)
        for j, item in enumerate(display_items[i:i+n_cols]):
            with cols[j]:
                st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item["qty"]} / {item["status"]}</div>', unsafe_allow_html=True)
                img = item["manual_url"] if item["manual_url"] else item["auto_url"]
                if img:
                    st.markdown(f'<div class="product-image-container"><img src="{img}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="product-image-container" style="background:#222;"><div style="color:#666;">NO IMAGE</div></div>', unsafe_allow_html=True)
                
                if not is_print_mode:
                    new_val = st.text_input("URL", value=item["manual_url"], key=f"url_{item['code']}")
                    if new_val != item["manual_url"]:
                        item["manual_url"] = new_val
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
