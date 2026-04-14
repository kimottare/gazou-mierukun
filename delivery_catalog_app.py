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
# 🎨 UI制御・視認性・レスポンシブ・印刷CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: #0e1117;
    }

    /* 1. ヘッダー：確実にボタンを表示させる設定 */
    [data-testid="stHeader"] {
        background-color: rgba(14, 17, 23, 0.8) !important;
        visibility: visible !important;
    }

    /* 2. 文字の視認性 */
    .main-title {
        font-size: 2.5rem !important; font-weight: 900 !important; color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        margin: 1rem 0 !important; border-left: 12px solid #ffffff; padding-left: 20px;
    }
    .product-title {
        font-weight: 800; font-size: 0.95rem; line-height: 1.2; height: 2.4em;
        overflow: hidden; margin-bottom: 4px; color: #ffffff !important;
        text-shadow: 2px 2px 5px rgba(0,0,0,1.0) !important;
    }
    .product-details {
        font-size: 0.72rem; color: #e0e0e0 !important; line-height: 1.3;
        height: 3.9em; overflow: hidden; margin-bottom: 8px;
        text-shadow: 1px 1px 3px rgba(0,0,0,1.0);
    }

    /* 3. 画像コンテナ */
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #333;
        overflow: hidden; margin-bottom: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.6);
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }

    /* 📱 スマホ表示：2列強制（iPhone Edge/Safari対応） */
    @media screen and (max-width: 800px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important; flex-direction: row !important;
            flex-wrap: wrap !important; width: 100% !important; gap: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: 50% !important; flex: 0 0 50% !important;
            min-width: 50% !important; max-width: 50% !important; padding: 6px !important;
        }
        .product-image-container { height: 150px !important; }
        .main-title { font-size: 1.5rem !important; border-left-width: 8px; padding-left: 12px; margin-top: 2rem !important; }
    }

    /* 🖨️ 印刷用：背景白・文字黒 */
    @media print {
        header, [data-testid="stSidebar"], .no-print, iframe, .stTextInput, .stAlert, hr { display: none !important; }
        body, .main, [data-testid="stAppViewContainer"] { background-color: white !important; color: black !important; }
        .main-title { color: #000 !important; text-shadow: none !important; border-left: 8px solid #000 !important; }
        .product-title { color: #000 !important; text-shadow: none !important; }
        .product-details { color: #333 !important; text-shadow: none !important; }
        .product-image-container { border: 1px solid #ddd !important; box-shadow: none !important; background: #fff !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 ロジック補助・画像検索（最大ヒット率） ---
def guess_column_index(columns, keywords, default_idx=0, exclude=[]):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            c_low = str(col).lower()
            if keyword.lower() in c_low and not any(ex.lower() in c_low for ex in exclude):
                return idx
    return default_idx

def is_valid_adidas_img(url):
    keywords = ["adidas", "yimg", "bing", "gstatic", "shop-adidas", "mm-adidas"]
    return any(k in url.lower() for k in keywords)

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()

    # 1. まず楽天APIで高精度検索
    try:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
        res = requests.get(url, params={"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code_str}", "hits": 3}, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                img_url = item["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                if code_str.lower() in item["Item"].get("itemName", "").lower():
                    return {"url": img_url}
    except: pass

    # 2. 楽天で見つからない場合はBing画像検索で広範に探す
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        bing_url = f"https://www.bing.com/images/search?q={query}"
        res = requests.get(bing_url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m_str = a.get('m')
            if m_str:
                murl = json.loads(m_str).get('murl')
                if murl and code_str.lower() in murl.lower() and is_valid_adidas_img(murl):
                    return {"url": murl}
                # 品番が含まれていなくてもadidas関連の画像なら許容
                if murl and "adidas" in murl.lower():
                    return {"url": murl}
    except: pass

    return None

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass 

# ==========================================
# メイン表示
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
    st.header("⚙️ 管理メニュー")
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード (5列)", value=False)
    
    if st.button("🖨️ 印刷する", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)

    if st.session_state.generated:
        st.write("---")
        st.subheader("🎯 絞り込み")
        is_new_only = st.checkbox("✨ 新規入荷のみ (#N/A)", key="new_only_toggle")
        
        items = st.session_state.catalog_items
        unique_bs = sorted(list(set([str(i["bs"]).strip() for i in items if i.get("bs") and not any(c.isdigit() for c in str(i["bs"])) and len(str(i["bs"])) > 2])))
        
        def set_all_bs(state):
            for b in unique_bs: st.session_state[f"chk_{b}"] = state

        c_btn1, c_btn2 = st.columns(2)
        c_btn1.button("全選択", on_click=set_all_bs, args=(True,), use_container_width=True)
        c_btn2.button("全解除", on_click=set_all_bs, args=(False,), use_container_width=True)
        
        sel_bs = []
        if unique_bs:
            with st.container(height=250):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}", value=st.session_state.get(f"chk_{b}", True)):
                        sel_bs.append(b)
        
        if st.button("🗑️ データをリセット"):
            if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
            st.session_state.catalog_items = []
            st.session_state.generated = False
            st.rerun()

# --- アップロード ---
if not st.session_state.generated:
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            # マルチシート対応の安全性確保
            if uploaded_file.name.endswith('.csv'):
                try: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='utf-8')
                except: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='cp932')
            else:
                xl = pd.ExcelFile(uploaded_file)
                sheet_names = xl.sheet_names
                if len(sheet_names) > 1:
                    selected_sheet = st.selectbox("読み込むシートを選択", sheet_names)
                else:
                    selected_sheet = sheet_names[0]
                df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, na_filter=False, dtype=str, header=None)

            # ヘッダー検知
            h_idx = 0
            for i, row in df.iterrows():
                valid_cells = sum(1 for v in row if str(v).strip() != "" and str(v).lower() != "nan")
                if valid_cells >= 3: 
                    h_idx = i; break
            df.columns = df.iloc[h_idx].tolist()
            df = df.iloc[h_idx+1:].reset_index(drop=True)

            # 🌟 プルダウン破壊防止：空白列や重複列を安全にリネーム
            raw_cols = [str(c).strip() if str(c).strip() and str(c).lower() != 'nan' else f"列{i+1}" for i, c in enumerate(df.columns)]
            cols = []
            seen = set()
            for c in raw_cols:
                new_c = c
                count = 1
                while new_c in seen:
                    new_c = f"{c}_{count}"
                    count += 1
                cols.append(new_c)
                seen.add(new_c)
            df.columns = cols

            # 🌟 列の自動紐付け（現場フォーマットを最優先）
            with st.expander("📋 列の紐付け確認", expanded=True):
                c1, c2, c3 = st.columns(3)
                art_c = c1.selectbox("品番 (Article)", cols, index=guess_column_index(cols, ['material number', 'art', 'code', '品番']))
                name_c = c2.selectbox("商品名称 (Name)", cols, index=guess_column_index(cols, ['名称', 'name', 'desc'], exclude=['size']))
                bs_c = c3.selectbox("BS (カテゴリー)", cols, index=guess_column_index(cols, ['bs', 'category', '部門'], exclude=['size', 'サイズ']))
                size_c = c1.selectbox("サイズ (Size)", cols, index=guess_column_index(cols, ['size description', 'size', 'サイズ']))
                qty_c = c2.selectbox("数量 (Qty)", cols, index=guess_column_index(cols, ['qty', '数量'], exclude=['inv qty']))
                status_c = c3.selectbox("ステータス (Status)", cols, index=guess_column_index(cols, ['inv qty', 'status', 'ステータス'], default_idx=min(11, len(cols)-1)))

            if st.button("カタログ作成開始", type="primary", use_container_width=True):
                results = []
                progress = st.progress(0)
                target_df = df[df[art_c].notnull() & (df[art_c] != "")].drop_duplicates(subset=[art_c])
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
        except Exception as e:
            st.error(f"読み込みエラーが発生しました: {e}")

# --- 📊 メイン表示 ---
if st.session_state.generated:
    display = [i for i in st.session_state.catalog_items if i.get("bs") in sel_bs]
    if is_new_only:
        display = [i for i in display if str(i.get("status", "")).upper() in ["#N/A", "#REF!", "NAN", "", "NEW"]]

    # 品番/合計表示
    total_q = sum([float(str(i.get("qty", "0")).replace(',','')) if str(i.get("qty", "0")).replace('.','',1).isdigit() else 0 for i in display])
    st.info(f"📊 **{len(display)}** 品番 / 合計 **{int(total_q)}** 点 を表示中")

    # スマホ転送
    st.markdown("<h3 class='no-print'>📱 スマホ転送</h3>", unsafe_allow_html=True)
    sid = st.session_state.get("share_id", uuid.uuid4().hex[:8]); st.session_state.share_id = sid
    get_shared_store()[sid] = display
    qr_html = f'<div style="text-align:center;"><div id="qrcode" style="display:inline-block;background:white;padding:10px;border-radius:8px;"></div></div><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><script>new QRCode(document.getElementById("qrcode"), {{text:window.parent.location.href.split("?")[0]+"?sid={sid}", width:120, height:120}});</script>'
    components.html(qr_html, height=150)

    # カタログ本体
    n_cols = 5 if is_print_mode else 3
    img_h = "140px" if is_print_mode else "200px"

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
                    # 🌟 Google画像検索リンク
                    st.markdown(f"🔍 [Google検索](https://www.google.com/search?tbm=isch&q=adidas+{item['code']})")
                    new_u = st.text_input("URL貼付", value=item["manual_url"], key=f"inp_{item['code']}")
                    if new_u != item["manual_url"]:
                        item["manual_url"] = new_u
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
