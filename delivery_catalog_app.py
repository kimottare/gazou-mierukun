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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

@st.cache_resource
def get_shared_store():
    return {}

st.set_page_config(page_title="商品画像見えるくん", layout="wide")

# ==========================================
# 🎨 UI/CSS設定
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
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 25px rgba(0,0,0,0.8) !important;
        margin-top: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        text-align: left;
        border-left: 12px solid #ffffff;
        padding-left: 20px;
    }
    .product-card { display: flex; flex-direction: column; height: 100%; }
    .product-info { display: flex; flex-direction: column; }
    .product-title {
        font-weight: 800; font-size: 1.0rem; line-height: 1.2; height: 2.4em;
        overflow: hidden; margin-bottom: 4px; color: #ffffff !important;
    }
    .product-image-container {
        display: flex; justify-content: center; align-items: center;
        background: #ffffff; border-radius: 8px; border: 1px solid #333;
        overflow: hidden; margin-bottom: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.6);
    }
    .product-image-container img { max-height: 100%; max-width: 100%; object-fit: contain; }
    .product-details { font-size: 0.75rem; color: #e0e0e0 !important; line-height: 1.3; height: 4.8em; overflow: hidden; }
    
    @media screen and (max-width: 800px) {
        .main-title { font-size: 1.6rem !important; }
        div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: column !important; gap: 0 !important; }
        .product-card { flex-direction: row !important; align-items: center; }
        .product-image-container { width: 90px !important; height: 90px !important; min-width: 90px; margin-right: 15px; }
    }

    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], .no-print, .stButton { display: none !important; }
        body, html, .stApp { background-color: white !important; }
        .product-title { color: #000 !important; }
        .product-image-container img { opacity: 1 !important; visibility: visible !important; display: block !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔍 診断機能 (Plan 1 & 2)
# ==========================================
def test_rakuten_api():
    """楽天APIの有効性をテストする"""
    test_code = "IG1024" # 代表的な品番
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {test_code}", "hits": 1}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return True, "✅ 正常: APIキーは有効です。"
        else:
            return False, f"❌ エラー: ステータスコード {res.status_code} ({res.text[:100]})"
    except Exception as e:
        return False, f"❌ 通信失敗: {str(e)}"

def test_bing_access():
    """Bing検索へのアクセスをテストする"""
    url = "https://www.bing.com/images/search?q=adidas"
    headers = {"User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return True, "✅ 正常: 検索サイトへアクセス可能です。"
        elif res.status_code == 403:
            return False, "❌ 拒否: サーバー(IP)がブロックされています(403)。"
        else:
            return False, f"❌ 制限: ステータスコード {res.status_code}"
    except Exception as e:
        return False, f"❌ 通信失敗: {str(e)}"

# ==========================================
# 🛠️ 各種ユーティリティ
# ==========================================
@st.dialog("データの全消去")
def confirm_reset():
    st.warning("全データを削除しますか？")
    if st.button("はい、削除します", type="primary"):
        st.session_state.catalog_items = []
        st.session_state.generated = False
        if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
        st.rerun()

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass

def format_date(d_str):
    if pd.isna(d_str) or str(d_str).strip() in ["", "nan", "NaT", "None"]: return "未定"
    s = str(d_str).strip()
    try:
        if s.replace('.', '', 1).isdigit():
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(s))).strftime('%Y/%m/%d')
        return pd.to_datetime(s).strftime('%Y/%m/%d')
    except: return s.split(" ")[0]

# --- 🔍 画像取得ロジック ---
def scrape_bing_high_res_images(query, code, limit=5):
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"}
    res_urls = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return [], f"Bing Error: {res.status_code}"
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m_str = a.get('m')
            if m_str:
                murl = json.loads(m_str).get('murl')
                if murl and str(code).strip().lower() in murl.lower():
                    if murl not in res_urls: res_urls.append(murl)
                    if len(res_urls) >= limit: break
        return res_urls, "Success"
    except Exception as e:
        return [], str(e)

def get_rakuten_images(code, limit=3):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 5, "imageFlag": 1}
    headers = {"User-Agent": USER_AGENT}
    res_urls = []
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code != 200: return [], f"Rakuten Error: {res.status_code}"
        items = res.json().get("Items", [])
        for item in items:
            img_urls = item["Item"].get("mediumImageUrls", [])
            for img in img_urls:
                img_url = img["imageUrl"].split("?_ex=")[0]
                if img_url not in res_urls: res_urls.append(img_url)
                if len(res_urls) >= limit: break
        return res_urls, "Success"
    except Exception as e:
        return [], str(e)

def get_best_images(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    r_urls, r_err = get_rakuten_images(code_str)
    b_urls, b_err = scrape_bing_high_res_images(query, code_str)
    combined = list(dict.fromkeys(r_urls + b_urls))
    return combined[:5], {"rakuten": r_err, "bing": b_err}

def guess_column_index(columns, keywords, default_idx=0, exclude=[]):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            c_low = str(col).lower()
            if keyword.lower() in c_low and not any(ex.lower() in c_low for ex in exclude):
                return idx
    return default_idx

# ==========================================
# メイン UI
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見えるくん</div>', unsafe_allow_html=True)

if "generated" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = False
    if "sid" in st.query_params:
        sid = st.query_params["sid"]
        if sid in get_shared_store():
            st.session_state.catalog_items = get_shared_store()[sid]
            st.session_state.generated = True
    elif os.path.exists(AUTO_SAVE_FILE):
        with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state.catalog_items = json.load(f)
            st.session_state.generated = True

with st.sidebar:
    st.header("⚙️ 設定・管理")
    
    # 🌟 プラン1&2の診断エリア
    with st.expander("🛠️ システム診断（デバッグ）", expanded=False):
        st.write("検索がうまくいかない時はこちらを確認")
        if st.button("診断開始", use_container_width=True):
            r_ok, r_msg = test_rakuten_api()
            b_ok, b_msg = test_bing_access()
            st.write(r_msg)
            st.write(b_msg)
            if not b_ok:
                st.error("⚠️ サーバーがブロックされています。プラン4（ローカル作成）を検討してください。")

    st.write("---")
    list_mode = st.radio("📋 リストモード", ["入荷リスト", "MKDリスト"])
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード")
    
    if st.button("🖨️ カタログを印刷", use_container_width=True):
        components.html("<script>window.parent.print();</script>", height=0)

    if st.session_state.generated:
        st.write("---")
        if st.button("🗑️ リセット", use_container_width=True): confirm_reset()

# --- 読み込み & 作成ロジック ---
if not st.session_state.generated:
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])
    if uploaded_file:
        df = pd.read_excel(uploaded_file, header=None) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None)
        # ヘッダー推測
        header_idx = 0
        for i, row in df.iterrows():
            if sum(1 for v in row if str(v).strip() != "" and str(v).lower() != "nan") >= 3:
                header_idx = i
                break
        df.columns = df.iloc[header_idx].tolist()
        df = df.iloc[header_idx+1:].reset_index(drop=True)
        columns = [str(c).strip() if str(c).strip() else f"列{i+1}" for i, c in enumerate(df.columns)]
        df.columns = columns

        with st.expander("📋 列割り当て確認", expanded=True):
            c1, c2, c3 = st.columns(3)
            code_col = c1.selectbox("Article", columns, index=guess_column_index(columns, ['art', 'code', '品番']))
            name_col = c2.selectbox("Name", columns, index=guess_column_index(columns, ['name', '名称', '商品名']))
            # 🌟 佐藤さんリクエスト：デフォルトを「列12」にする
            status_col = c3.selectbox("Status", ["(なし)"] + columns, index=guess_column_index(columns, ['status', '列12'], default_idx=-1)+1)
            qty_col = c1.selectbox("Qty", ["(なし)"] + columns, index=guess_column_index(columns, ['qty', '数量'])+1)
            bs_col = c2.selectbox("BS", ["(なし)"] + columns, index=guess_column_index(columns, ['bs', 'category'])+1)

        if st.button("カタログ作成開始", type="primary", use_container_width=True):
            display_df = df[df[code_col].astype(str).str.strip() != ""].drop_duplicates(subset=[code_col])
            st.info(f"自動検索中... ({len(display_df)}件)")
            p_bar = st.progress(0)
            
            results = []
            def fetch_item(args):
                idx, row = args
                code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                urls, errs = get_best_images(code, name)
                return idx, {"code": code, "name": name, "bs": str(row.get(bs_col, "")), "qty": str(row.get(qty_col, "0")),
                            "status": str(row.get(status_col, "")), "auto_url": urls[0] if urls else None, 
                            "auto_urls": urls, "errors": errs}

            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                futures = [exe.submit(fetch_item, (i, row)) for i, (_, row) in enumerate(display_df.iterrows())]
                for i, f in enumerate(concurrent.futures.as_completed(futures)):
                    results.append(f.result())
                    p_bar.progress((i + 1) / len(display_df))
            
            results.sort(key=lambda x: x[0])
            st.session_state.catalog_items = [r[1] for r in results]
            st.session_state.generated = True
            save_auto_save_data(st.session_state.catalog_items)
            st.rerun()

# --- 表示エリア ---
if st.session_state.generated:
    filtered = st.session_state.catalog_items
    st.info(f"📊 {len(filtered)} 品番を表示中")

    num_cols = 5 if is_print_mode else 3
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols)
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                url = item.get("auto_url")
                img_tag = f'<img src="{url}" loading="eager">' if url else '<div style="color:#666;">画像なし</div>'
                html_card = f'<div class="product-card"><div class="product-image-container">{img_tag}</div><div class="product-info"><div class="product-title">{item["name"]}</div><div class="product-details">Art: {item["code"]}<br>Qty: {item["qty"]}<br>Status: {item["status"]}</div></div></div>'
                st.markdown(html_card, unsafe_allow_html=True)
                
                # 🌟 プラン1：画像が出なかった場合のみ、エラー理由を表示する
                if not url and not st.query_params.get("sid"):
                    with st.expander("🔍 なぜ画像がない？", expanded=False):
                        st.caption(f"楽天: {item.get('errors', {}).get('rakuten')}")
                        st.caption(f"Bing: {item.get('errors', {}).get('bing')}")
