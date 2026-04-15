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

st.set_page_config(page_title="商品画像見えるくん", layout="wide")

# ==========================================
# 🎨 究極の視認性・スマホ1列リスト強制 ＋ 画像拡大機能
# ==========================================
st.markdown("""
    <style>
    /* 🌟 全体の背景をダークモードに固定 */
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

    /* 🌟 カード全体と情報エリアのラッパー */
    .product-card {
        display: flex;
        flex-direction: column; 
        height: 100%;
    }
    .product-info {
        display: flex;
        flex-direction: column;
    }

    .product-title {
        font-weight: 800;
        font-size: 1.0rem;
        line-height: 1.2;
        height: 2.4em;
        overflow: hidden;
        margin-bottom: 4px;
        color: #ffffff !important;
        text-shadow: 2px 2px 5px rgba(0,0,0,1.0) !important;
    }

    .product-image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #333;
        overflow: hidden;
        margin-bottom: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.6);
    }

    .product-image-container img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
        opacity: 1 !important;
        filter: brightness(1.05) contrast(1.05) !important;
    }

    .product-details {
        font-size: 0.75rem;
        color: #e0e0e0 !important;
        line-height: 1.3;
        height: 4.8em; 
        overflow: hidden;
        margin-bottom: 8px;
        text-shadow: 1px 1px 3px rgba(0,0,0,1.0);
    }

    /* 🌟 画像拡大（ライトボックス）機能のCSS */
    .lightbox-toggle { display: none; }
    .lightbox {
        display: none;
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: rgba(0, 0, 0, 0.85);
        z-index: 9999999;
        justify-content: center;
        align-items: center;
        backdrop-filter: blur(5px);
    }
    .lightbox img {
        max-width: 95vw; max-height: 95vh;
        object-fit: contain;
        border-radius: 8px;
        box-shadow: 0 4px 25px rgba(0,0,0,0.8);
        position: relative;
        z-index: 2;
    }
    .lightbox-toggle:checked + .lightbox {
        display: flex;
    }
    .lightbox-close-area {
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        cursor: zoom-out;
        z-index: 1;
    }
    .product-image-container label {
        cursor: zoom-in;
        width: 100%; height: 100%;
        display: flex; justify-content: center; align-items: center;
        margin: 0; padding: 0;
    }

    footer {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}

    /* ==========================================
       📱 モバイル表示（スマホ）の1列リスト化
       ========================================== */
    @media screen and (max-width: 800px) {
        .main-title {
            font-size: 1.6rem !important;
            border-left-width: 8px;
            padding-left: 12px;
            margin-top: 1rem !important;
        }

        /* 1カラム（縦1列）リストに強制 */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important; 
            gap: 0 !important;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: 100% !important;
            max-width: 100% !important;
            padding: 12px 0 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1); 
        }

        /* 横並びレイアウトに変更 */
        .product-card {
            flex-direction: row !important;
            align-items: center;
            margin-bottom: 4px;
        }

        .product-image-container {
            width: 90px !important;
            height: 90px !important; 
            min-width: 90px;
            margin-bottom: 0 !important;
            margin-right: 15px;
            border-radius: 6px;
            box-shadow: none !important; 
        }

        .product-info {
            flex-grow: 1;
            overflow: hidden; 
        }

        .product-title {
            font-size: 1.0rem !important;
            height: auto !important;
            white-space: nowrap; 
            text-overflow: ellipsis; 
            margin-bottom: 4px;
        }

        .product-details {
            font-size: 0.70rem !important;
            height: auto !important;
            text-shadow: none !important;
            color: #bbb !important;
        }
    }

    /* 4. 印刷用設定 */
    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, [data-testid="stExpander"],
        [data-testid="stMultiSelect"], [data-testid="stCheckbox"], 
        .no-print, .stTabs, iframe, .stTextInput, .stAlert, hr {
            display: none !important;
        }
        .main .block-container {
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        body, html, [data-testid="stAppViewContainer"], .stApp { background-color: white !important; }
        .product-title { color: #000 !important; text-shadow: none !important; font-size: 0.85rem; }
        .product-details { color: #333 !important; text-shadow: none !important; font-size: 0.65rem; }
        .product-image-container { border: 1px solid #aaa !important; box-shadow: none !important; }
        .product-image-container img { filter: none !important; }
        .lightbox, .lightbox-toggle { display: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 削除確認ダイアログ
# ==========================================
@st.dialog("データの全消去")
def confirm_reset():
    st.warning("現在表示されているリストと保存データをすべて削除します。よろしいですか？")
    c1, c2 = st.columns(2)
    if c1.button("はい、削除します", type="primary", use_container_width=True):
        st.session_state.generated = False
        st.session_state.catalog_items = []
        if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
        st.query_params.clear()
        st.rerun()
    if c2.button("いいえ", use_container_width=True):
        st.rerun()

def generate_html_report(items):
    now_str = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
    html_content = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>カタログ出力</title><style>body{{font-family:sans-serif;background:#fff;padding:20px;}} .grid{{display:grid;grid-template-columns:repeat(5, 1fr);gap:10px;}} .card{{border:1px solid #eee;padding:10px;border-radius:5px;break-inside:avoid;}} .img-box{{height:150px;display:flex;justify-content:center;align-items:center;}} img{{max-height:100%;max-width:100%;object-fit:contain;}} .t{{font-weight:bold;font-size:0.8rem;margin:5px 0;}} .d{{font-size:0.65rem;color:#666;}}</style></head><body><h3>📦 商品カタログ ({len(items)}件)</h3><div class="grid">"""
    for item in items:
        u = item.get("manual_url") or item.get("auto_url") or ""
        if item.get("mode") == "MKD":
            details_html = f'Art:{item["code"]}<br>Price:{item.get("price","")}<br>Gender:{item.get("gender","")}<br>Date:{item.get("date","")}<br>Qty:{item.get("qty","0")}'
        else:
            details_html = f'Art:{item["code"]}<br>{item.get("size","")}<br>{item.get("qty","0")}点 / {item.get("status","")}'
            
        html_content += f'<div class="card"><div class="img-box"><img src="{u}"></div><div class="t">{item.get("name","")}</div><div class="d">{details_html}</div></div>'
    html_content += f"</div><p style='text-align:center;font-size:0.6rem;'>出力:{now_str}</p></body></html>"
    return html_content

# --- 🔍 究極の検索ロジック ---
def is_valid_adidas_img(url):
    keywords = ["adidas", "yimg", "bing", "gstatic", "shop-adidas", "mm-adidas"]
    return any(k in url.lower() for k in keywords)

def scrape_bing_high_res_images(query, code, limit=5):
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res_urls = []
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m_str = a.get('m')
            if m_str:
                murl = json.loads(m_str).get('murl')
                if murl and str(code).strip().lower() in murl.lower() and is_valid_adidas_img(murl):
                    if murl not in res_urls:
                        res_urls.append(murl)
                    if len(res_urls) >= limit: break
    except: pass
    return res_urls

def get_rakuten_images(code, limit=3):
    if not RAKUTEN_APP_ID: return []
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 5, "imageFlag": 1}
    res_urls = []
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                if str(code).strip().lower() in item["Item"].get("itemName", "").lower():
                    img_urls = item["Item"].get("mediumImageUrls", [])
                    for img in img_urls:
                        img_url = img["imageUrl"].split("?_ex=")[0]
                        if img_url not in res_urls:
                            res_urls.append(img_url)
                        if len(res_urls) >= limit: break
                if len(res_urls) >= limit: break
    except: pass
    return res_urls

def get_best_images(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    r_urls = get_rakuten_images(code_str, limit=3)
    b_urls = scrape_bing_high_res_images(query, code_str, limit=5)
    
    combined = []
    for u in r_urls:
        if u not in combined: combined.append(u)
    for u in b_urls:
        if u not in combined: combined.append(u)
        
    return combined[:5]

def guess_column_index(columns, keywords, default_idx=0, exclude=[]):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            c_low = str(col).lower()
            if keyword.lower() in c_low and not any(ex.lower() in c_low for ex in exclude):
                return idx
    return default_idx

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass 

# ==========================================
# メイン UI 
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見えるくん</div>', unsafe_allow_html=True)

if "generated" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = False
    if "sid" in st.query_params:
        try:
            sid = st.query_params["sid"]
            if sid in get_shared_store():
                st.session_state.catalog_items = get_shared_store()[sid]
                st.session_state.generated = True
        except: pass
    elif os.path.exists(AUTO_SAVE_FILE):
        try:
            with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
                st.session_state.catalog_items = json.load(f)
                st.session_state.generated = True
        except: pass

with st.sidebar:
    st.header("⚙️ 設定・管理")
    
    list_mode = st.radio("📋 リストモード", ["入荷リスト", "MKDリスト"], index=0)
    st.write("---")
    
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.button("🖨️ カタログを印刷", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)

    st.write("---")
    
    if st.session_state.generated:
        st.subheader("🎯 絞り込み")
        
        is_new_only = st.checkbox("✨ 新規入荷のみ (入荷リスト用)", key="new_only_toggle")

        items = st.session_state.catalog_items
        unique_bs = sorted(list(set([i["bs"] for i in items if i.get("bs")])))
        
        def set_all_bs(state):
            for b in unique_bs: st.session_state[f"chk_{b}"] = state

        c_btn1, c_btn2 = st.columns(2)
        c_btn1.button("全選択", on_click=set_all_bs, args=(True,), use_container_width=True)
        c_btn2.button("全解除", on_click=set_all_bs, args=(False,), use_container_width=True)
        
        sel_bs = []
        if unique_bs:
            with st.container(height=200):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}"): sel_bs.append(b)
        
        st.write("---")
        if st.button("🗑️ リセット", type="secondary", use_container_width=True):
            confirm_reset()

if not st.session_state.generated:
    st.subheader(f"📝 新規リストを作成 ({list_mode})")
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])
    
    if uploaded_file:
        try:
            if list_mode == "入荷リスト":
                if uploaded_file.name.endswith('.csv'):
                    try: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='utf-8')
                    except: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='cp932')
                else:
                    xl = pd.ExcelFile(uploaded_file)
                    sheet_names = xl.sheet_names
                    selected_sheet = st.selectbox("読み込むシートを選択", sheet_names) if len(sheet_names) > 1 else sheet_names[0]
                    df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, na_filter=False, dtype=str, header=None)
                
                header_idx = 0
                for i, row in df.iterrows():
                    row_vals = [str(v) for v in row if v is not None]
                    if sum(1 for v in row_vals if v.strip() != "" and v.lower() != "nan") >= 3:
                        header_idx = i
                        break
                df.columns = df.iloc[header_idx].tolist()
                df = df.iloc[header_idx+1:].reset_index(drop=True)
                columns = [str(c).strip() if str(c).strip() and str(c).lower() != 'nan' else f"列{i+1}" for i, c in enumerate(df.columns)]
                df.columns = columns
                
                with st.expander("📋 列割り当て確認", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        code_col = st.selectbox("Article", columns, index=guess_column_index(columns, ['material number', 'artno', 'article', 'art', 'code', '品番']))
                        size_col = st.selectbox("Size", ["(なし)"] + columns, index=guess_column_index(columns, ['size description', 'size', 'サイズ'])+1)
                    with c2:
                        name_col = st.selectbox("Name", columns, index=guess_column_index(columns, ['商品名称', '名称', 'name', 'item', 'description'], exclude=['size', 'サイズ', '店舗', 'store']))
                        qty_col = st.selectbox("Qty", ["(なし)"] + columns, index=guess_column_index(columns, ['qty', '数量'], exclude=['inv qty'])+1)
                    with c3:
                        bs_col = st.selectbox("BS (カテゴリー)", ["(なし)"] + columns, index=guess_column_index(columns, ['bs', 'category'], exclude=['size', 'サイズ', 'j/'], default_idx=-1)+1)
                        status_col = st.selectbox("Status", ["(なし)"] + columns, index=guess_column_index(columns, ['inv qty', 'status', 'ステータス'], default_idx=-1)+1)

            elif list_mode == "MKDリスト":
                if uploaded_file.name.endswith('.csv'):
                    try: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=4, encoding='utf-8')
                    except: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=4, encoding='cp932')
                else:
                    xl = pd.ExcelFile(uploaded_file)
                    sheet_names = xl.sheet_names
                    selected_sheet = st.selectbox("読み込むシートを選択", sheet_names) if len(sheet_names) > 1 else sheet_names[0]
                    df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, na_filter=False, dtype=str, header=4)
                
                columns = [str(c).strip() for c in df.columns]
                df.columns = columns
                
                with st.expander("📋 列割り当て確認 (MKD)", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        code_col = st.selectbox("商品番号", columns, index=guess_column_index(columns, ['material number', 'code', 'art']))
                        name_col = st.selectbox("商品名", columns, index=guess_column_index(columns, ['model name', 'name']))
                    with c2:
                        price_col = st.selectbox("NEW Price tax", columns, index=guess_column_index(columns, ['new price tax', 'price']))
                        gender_col = st.selectbox("ジェンダー", columns, index=guess_column_index(columns, ['gender']))
                    with c3:
                        qty_col = st.selectbox("数量", columns, index=guess_column_index(columns, ['inv qty', 'qty']))
                        date_col = st.selectbox("MKD/MKU Start Date", columns, index=guess_column_index(columns, ['mkd/mku start date', 'date']))
                        bs_col = st.selectbox("BS (カテゴリー)", ["(なし)"] + columns, index=guess_column_index(columns, ['business segment', 'bs'], exclude=['size', 'サイズ', 'j/'], default_idx=-1)+1)

            if st.button("カタログ作成開始", type="primary", use_container_width=True):
                display_df = df[df[code_col].astype(str).str.strip() != ""]
                
                if list_mode == "入荷リスト":
                    agg_sizes, agg_qtys, agg_is_new = {}, {}, {}
                    
                    for code, group in display_df.groupby(code_col):
                        code_str = str(code).strip()
                        size_dict, total_qty = {}, 0
                        is_all_new = True  # 🌟 ここが新しい厳格判定ロジック
                        
                        for _, row in group.iterrows():
                            s_val, q_val = str(row[size_col]).strip() if size_col != "(なし)" else "", str(row[qty_col]).strip() if qty_col != "(なし)" else "0"
                            try: q_num = float(q_val)
                            except: q_num = 0
                            total_qty += q_num
                            if s_val: size_dict[s_val] = size_dict.get(s_val, 0) + q_num
                            
                            # 🌟 すべてのサイズにおいてステータスがエラーか空白かをチェック
                            stat_val = str(row[status_col]).strip().upper() if status_col != "(なし)" else ""
                            if stat_val not in ["#N/A", "#REF!", "NAN", ""]:
                                is_all_new = False
                                
                        agg_sizes[code_str] = ", ".join([f"{s}({int(q) if q==int(q) else q})" for s, q in size_dict.items()])
                        agg_qtys[code_str] = str(int(total_qty) if total_qty == int(total_qty) else total_qty)
                        agg_is_new[code_str] = is_all_new

                    display_df = display_df.drop_duplicates(subset=[code_col])
                    st.info(f"自動検索中... ({len(display_df)}件)")
                    p_bar = st.progress(0)
                    
                    def fetch_data(args):
                        idx, row = args
                        code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                        if not code or code.lower() in ['nan', 'none']: return idx, None
                        urls = get_best_images(code, name)
                        top_url = urls[0] if urls else None
                        return idx, {"mode": "入荷", "code": code, "name": name, "bs": str(row[bs_col]) if bs_col != "(なし)" else "",
                                   "size": agg_sizes.get(code, ""), "qty": agg_qtys.get(code, "0"),
                                   "status": str(row[status_col]) if status_col != "(なし)" else "",
                                   "is_new": agg_is_new.get(code, False), # 🌟 保存データに新規判定結果を含める
                                   "auto_url": top_url, "auto_urls": urls, "manual_url": ""}
                
                elif list_mode == "MKDリスト":
                    agg_qtys = {}
                    for code, group in display_df.groupby(code_col):
                        code_str = str(code).strip()
                        total_qty = 0
                        for _, row in group.iterrows():
                            q_val = str(row[qty_col]).strip() if qty_col != "(なし)" else "0"
                            try: q_num = float(q_val)
                            except: q_num = 0
                            total_qty += q_num
                        agg_qtys[code_str] = str(int(total_qty) if total_qty == int(total_qty) else total_qty)

                    display_df = display_df.drop_duplicates(subset=[code_col])
                    st.info(f"自動検索中... ({len(display_df)}件)")
                    p_bar = st.progress(0)
                    
                    def fetch_data(args):
                        idx, row = args
                        code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                        if not code or code.lower() in ['nan', 'none']: return idx, None
                        urls = get_best_images(code, name)
                        top_url = urls[0] if urls else None
                        return idx, {"mode": "MKD", "code": code, "name": name, "bs": str(row[bs_col]) if bs_col != "(なし)" else "",
                                   "price": str(row[price_col]), "gender": str(row[gender_col]), "date": str(row[date_col]),
                                   "qty": agg_qtys.get(code, "0"),
                                   "auto_url": top_url, "auto_urls": urls, "manual_url": ""}

                unsorted = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                    futures = [exe.submit(fetch_data, (i, row)) for i, (_, row) in enumerate(display_df.iterrows())]
                    for i, f in enumerate(concurrent.futures.as_completed(futures)):
                        idx, res = f.result()
                        if res: unsorted.append((idx, res))
                        p_bar.progress((i + 1) / len(display_df))
                unsorted.sort(key=lambda x: x[0])
                st.session_state.catalog_items = [item for _, item in unsorted]
                st.session_state.generated = True
                save_auto_save_data(st.session_state.catalog_items)
                st.rerun()
        except Exception as e: st.error(f"エラー: {e}")

if st.session_state.generated:
    items = st.session_state.catalog_items
    filtered = items
    
    if sel_bs:
        filtered = [i for i in filtered if i["bs"] in sel_bs]
    
    # 🌟 新規入荷のみをONにした場合、厳格判定ロジック(is_new)を参照する
    if is_new_only:
        filtered = [i for i in filtered if i.get("is_new", str(i.get("status", "")).strip().upper() in ["#N/A", "#REF!", "NAN", ""])]

    total_q = sum([float(i.get("qty",0)) if i.get("qty") else 0 for i in filtered])
    
    if not is_print_mode:
        st.info(f"📊 **{len(filtered)}** 品番 / 合計 **{int(total_q)}** 点 を表示中")
    else:
        st.caption(f"【コンパクトモード】 {len(filtered)} 品番 / {int(total_q)} 点")

    st.markdown("<h3 class='no-print'>📱 スマホ転送・出力</h3>", unsafe_allow_html=True)
    btn1, btn2 = st.columns(2)
    with btn1:
        st.download_button("HTMLファイルとして保存", generate_html_report(filtered), "catalog.html", "text/html", use_container_width=True, type="primary")
    with btn2:
        sid = st.session_state.get("share_id", uuid.uuid4().hex[:8]); st.session_state.share_id = sid
        get_shared_store()[sid] = filtered
        qr_html = f'<div style="display:flex; justify-content:center;"><div id="qrcode" style="background:white;padding:10px;border-radius:8px;"></div></div><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><script>var url = window.parent.location.href.split("?")[0] + "?sid={sid}"; new QRCode(document.getElementById("qrcode"), {{text:url, width:120, height:120}});</script>'
        components.html(qr_html, height=150)

    num_cols = 5 if is_print_mode else 3
    img_h = "140px" if is_print_mode else "260px"
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols) 
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                url = item.get("manual_url") or item.get("auto_url")
                
                if url:
                    img_id = f"img_modal_{i}_{j}"
                    img_tag = f'<label for="{img_id}"><img src="{url}"></label><input type="checkbox" id="{img_id}" class="lightbox-toggle"><div class="lightbox"><label for="{img_id}" class="lightbox-close-area"></label><img src="{url}"></div>'
                else:
                    img_tag = '<div style="color:#999; font-size:0.8rem;">画像なし</div>'
                
                if item.get("mode") == "MKD":
                    details_html = f'Art: {item["code"]}<br>Price: {item.get("price","")}<br>Gender: {item.get("gender","")}<br>Date: {item.get("date","")}<br>Qty: {item.get("qty","0")}'
                else:
                    details_html = f'Art: {item["code"]}<br>Size: {item.get("size","")}<br>Qty: {item.get("qty","0")}点 / {item.get("status","")}'

                html_card = f'<div class="product-card"><div class="product-image-container" style="height:{img_h};">{img_tag}</div><div class="product-info"><div class="product-title">{item["name"]}</div><div class="product-details">{details_html}</div></div></div>'
                st.markdown(html_card, unsafe_allow_html=True)
                
                if not is_print_mode:
                    with st.expander("🔍 画像変更・検索", expanded=False):
                        if "auto_urls" not in item:
                            st.warning("⚠️ 過去のデータです。候補画像機能を使うには、リセットしてリストを再作成してください。")
                        else:
                            candidates = item.get("auto_urls", [])
                            if candidates:
                                st.markdown("<div style='font-size:0.75rem; color:#aaa; margin-bottom:4px;'>▼ 候補から選ぶ（左右スクロール）</div>", unsafe_allow_html=True)
                                cand_html = "<div style='display:flex; overflow-x:auto; gap:8px; padding-bottom:8px;'>"
                                for c_idx, c_url in enumerate(candidates):
                                    cand_html += f"<div style='flex-shrink:0; text-align:center;'><img src='{c_url}' style='height:80px; width:80px; object-fit:contain; background:#fff; border-radius:4px; border:1px solid #555;'><div style='font-size:0.75rem; margin-top:2px;'>No.{c_idx+1}</div></div>"
                                cand_html += "</div>"
                                st.markdown(cand_html, unsafe_allow_html=True)
                                c1, c2 = st.columns([2, 1])
                                with c1:
                                    sel_idx = st.radio("番号", options=range(1, len(candidates)+1), horizontal=True, label_visibility="collapsed", key=f"rad_{item['code']}")
                                with c2:
                                    if st.button("✓ 変更", key=f"btn_apply_{item['code']}", use_container_width=True):
                                        item["manual_url"] = candidates[sel_idx - 1]
                                        save_auto_save_data(st.session_state.catalog_items)
                                        st.rerun()
                                st.write("---")
                            else:
                                st.info("💡 他の候補画像が見つかりませんでした。")
                        st.markdown(f"<div class='no-print' style='margin-bottom:8px;'><a href='https://www.google.com/search?tbm=isch&q=adidas+{item['code']}' target='_blank'>🌐 Google画像検索を開く</a></div>", unsafe_allow_html=True)
                        new_u = st.text_input("URLを手動貼付", value=item.get("manual_url", ""), key=f"inp_{item['code']}")
                        if new_u != item.get("manual_url"):
                            item["manual_url"] = new_u
                            save_auto_save_data(st.session_state.catalog_items)
                            st.rerun()
