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
# 🎨 究極の視認性・コンパクト・モバイル2列絶対強制CSS
# ==========================================
st.markdown("""
    <style>
    /* 1. タイトルの視認性（白文字 + 強力なシャドウ） */
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

    /* 2. 商品名称の視認性（白文字 + 影） */
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

    /* 3. 画像コンテナ（等高・整列） */
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

    /* 画像をハッキリ表示（薄さを解消） */
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
        height: 3.9em;
        overflow: hidden;
        margin-bottom: 8px;
        text-shadow: 1px 1px 3px rgba(0,0,0,1.0);
    }

    /* メニューボタンを消さないように調整 */
    footer {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stHeader"] {
        background: transparent !important;
    }

    /* ==========================================
       📱 モバイル表示（スマホ）の2列強制・絶対命令
       ========================================== */
    @media screen and (max-width: 800px) {
        .main-title {
            font-size: 1.6rem !important;
            border-left-width: 8px;
            padding-left: 12px;
            margin-top: 1rem !important;
        }

        /* 1カラム化（縦並び）を完全に阻止し、横2列を死守する */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            width: 100% !important;
            gap: 0 !important;
        }

        /* 各カラム要素を確実に50%幅で固定する */
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: 50% !important;
            flex: 0 0 50% !important;
            min-width: 50% !important;
            max-width: 50% !important;
            padding: 8px !important;
        }

        .product-title {
            font-size: 0.85rem !important;
            height: 2.4em !important;
            margin-bottom: 2px;
        }
        .product-details {
            font-size: 0.65rem !important;
            height: 3.9em !important;
            margin-bottom: 4px;
        }
        
        .product-image-container {
            height: 150px !important;
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
        body { background-color: white !important; }
        .product-title { color: #000 !important; text-shadow: none !important; font-size: 0.85rem; }
        .product-details { color: #333 !important; text-shadow: none !important; font-size: 0.65rem; }
        .product-image-container { border: 1px solid #eee; box-shadow: none; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# ダイアログ・関数
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
    for i in items:
        u = i.get("manual_url") or i.get("auto_url") or ""
        html_content += f'<div class="card"><div class="img-box"><img src="{u}"></div><div class="t">{i.get("name","")}</div><div class="d">Art:{i.get("code","")}<br>{i.get("size","")}<br>{i.get("qty","")}点 / {i.get("status","")}</div></div>'
    html_content += f"</div><p style='text-align:center;font-size:0.6rem;'>出力:{now_str}</p></body></html>"
    return html_content

# --- 🔍 検索ロジック ---
def is_valid_adidas_img(url):
    keywords = ["adidas", "yimg", "bing", "gstatic", "shop-adidas", "mm-adidas"]
    return any(k in url.lower() for k in keywords)

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
                if murl and str(code).strip().lower() in murl.lower() and is_valid_adidas_img(murl):
                    return murl, True
    except: pass
    return None, False

def get_rakuten_image(code):
    if not RAKUTEN_APP_ID: return None, False
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 3, "imageFlag": 1}
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                img_url = item["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                if str(code).strip().lower() in item["Item"].get("itemName", "").lower():
                    return img_url, True
    except: pass
    return None, False

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    rak_url, rak_exact = get_rakuten_image(code_str)
    if rak_exact: return {"url": rak_url, "source": "楽天公式"}
    bing_url, bing_exact = scrape_bing_high_res_image(query, code_str)
    if bing_exact: return {"url": bing_url, "source": "Bing検索"}
    return None

def guess_column_index(columns, keywords, default_idx=0):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            if keyword in str(col).lower(): return idx
    return default_idx

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass 

# ==========================================
# メイン UI 
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

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
    # ⚡ デフォルト検索スピードを5に固定
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.button("🖨️ カタログを印刷", use_container_width=True, type="primary"):
        components.html("<script>window.parent.print();</script>", height=0)

    st.write("---")
    
    # 🎯 絞り込みセクション
    if st.session_state.generated:
        st.subheader("🎯 絞り込み")
        
        # ✨ 新規入荷のみチェック
        is_new_only = st.checkbox("✨ 新規入荷のみ", key="new_only_toggle")

        items = st.session_state.catalog_items
        # 👇 【修正】カテゴリー(BS)を正しく抽出
        unique_bs = sorted(list(set([str(i["bs"]) for i in items if i.get("bs") and str(i.get("bs")).strip() != ""])))
        
        def set_all_bs(state):
            for b in unique_bs: st.session_state[f"chk_{b}"] = state

        c_btn1, c_btn2 = st.columns(2)
        c_btn1.button("全選択", on_click=set_all_bs, args=(True,), use_container_width=True)
        c_btn2.button("全解除", on_click=set_all_bs, args=(False,), use_container_width=True)
        
        sel_bs = []
        if unique_bs:
            with st.container(height=200):
                # 👇 【修正】ここがサイズではなくカテゴリー(BS)であることを保証
                for b in unique_bs:
                    if st.checkbox(f"BS: {b}", key=f"chk_{b}"): sel_bs.append(b)
        
        st.write("---")
        if st.button("🗑️ リセット", type="secondary", use_container_width=True):
            confirm_reset()

if not st.session_state.generated:
    st.subheader("📝 新規リストを作成")
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                try: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='utf-8')
                except: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='cp932')
            else: df = pd.read_excel(uploaded_file, na_filter=False, dtype=str, header=None)
            
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

            with st.expander("📋 列割り当て確認"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    code_col = st.selectbox("Article", columns, index=guess_column_index(columns, ['artno', 'article', 'art', 'code']))
                    size_col = st.selectbox("Size", columns, index=guess_column_index(columns, ['size', 'サイズ']))
                with c2:
                    name_col = st.selectbox("Name", columns, index=guess_column_index(columns, ['商品名称', '名称', 'name', 'item']))
                    qty_col = st.selectbox("Qty", columns, index=guess_column_index(columns, ['qty', '数量']))
                with c3:
                    # 👇 【修正】カテゴリー(BS)の自動検出キーワードを強化
                    bs_col = st.selectbox("BS (カテゴリー)", columns, index=guess_column_index(columns, ['bs', 'category', '部門', 'カテゴリ', 'division']))
                    status_col = st.selectbox("Status", ["(なし)"] + columns, index=len(columns))

            if st.button("カタログ作成開始", type="primary", use_container_width=True):
                display_df = df[df[code_col].astype(str).str.strip() != ""]
                agg_sizes, agg_qtys = {}, {}
                for code, group in display_df.groupby(code_col):
                    code_str = str(code).strip()
                    size_dict, total_qty = {}, 0
                    for _, row in group.iterrows():
                        s_val, q_val = str(row[size_col]).strip(), str(row[qty_col]).strip()
                        try: q_num = float(q_val)
                        except: q_num = 0
                        total_qty += q_num
                        if s_val: size_dict[s_val] = size_dict.get(s_val, 0) + q_num
                    agg_sizes[code_str] = ", ".join([f"{s}({int(q) if q==int(q) else q})" for s, q in size_dict.items()])
                    agg_qtys[code_str] = str(int(total_qty) if total_qty == int(total_qty) else total_qty)

                display_df = display_df.drop_duplicates(subset=[code_col])
                st.info(f"自動検索中... ({len(display_df)}件)")
                p_bar = st.progress(0)
                def fetch_data(args):
                    idx, row = args
                    code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                    if not code or code.lower() in ['nan', 'none']: return idx, None
                    img = get_best_image(code, name)
                    # 👇 【修正】ここでBSに確実にカテゴリー列のデータを入れる
                    return idx, {"code": code, "name": name, "bs": str(row[bs_col]).strip() if bs_col != "(なし)" else "",
                               "size": agg_sizes.get(code, ""), "qty": agg_qtys.get(code, ""),
                               "status": str(row[status_col]) if status_col != "(なし)" else "",
                               "auto_url": img["url"] if img else None, "source": img["source"] if img else None, "manual_url": ""}
                
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
    # 絞り込みロジックの適用
    items = st.session_state.catalog_items
    filtered = items
    
    if sel_bs:
        filtered = [i for i in filtered if i["bs"] in sel_bs]
    
    if is_new_only:
        filtered = [i for i in filtered if str(i.get("status", "")).strip().upper() in ["#N/A", "#REF!", "NAN", ""]]

    # UI表示
    total_q = sum([float(i.get("qty",0)) if i.get("qty") else 0 for i in filtered])
    
    if not is_print_mode:
        st.info(f"📊 **{len(filtered)}** 品番 / 合計 **{int(total_q)}** 点 を表示中")
    else:
        st.caption(f"【コンパクトモード】 {len(filtered)} 品番 / {int(total_q)} 点")

    # 📱 スマホ転送・出力セクション
    st.markdown("<h3 class='no-print'>📱 スマホ転送・出力</h3>", unsafe_allow_html=True)
    btn1, btn2 = st.columns(2)
    with btn1:
        st.download_button("HTMLファイルとして保存", generate_html_report(filtered), "catalog.html", "text/html", use_container_width=True, type="primary")
    with btn2:
        sid = st.session_state.get("share_id", uuid.uuid4().hex[:8]); st.session_state.share_id = sid
        get_shared_store()[sid] = filtered
        qr_html = f'<div style="display:flex; justify-content:center;"><div id="qrcode" style="background:white;padding:10px;border-radius:8px;"></div></div><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><script>var url = window.parent.location.href.split("?")[0] + "?sid={sid}"; new QRCode(document.getElementById("qrcode"), {{text:url, width:120, height:120}});</script>'
        components.html(qr_html, height=150)

    # カタログ本体
    num_cols = 5 if is_print_mode else 3
    img_h = "140px" if is_print_mode else "260px"
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols) 
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item.get("qty","0")}点 / {item["status"]}</div>', unsafe_allow_html=True)
                
                url = item.get("manual_url") or item.get("auto_url")
                if url: st.markdown(f'<div class="product-image-container" style="height:{img_h};"><img src="{url}"></div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="product-image-container" style="height:{img_h}; background:#f8f9fa;"><div style="color:#999; font-size:0.8rem;">画像なし</div></div>', unsafe_allow_html=True)
                
                if not is_print_mode:
                    st.markdown(f"🔍 [Google検索](https://www.google.com/search?tbm=isch&q=adidas+{item['code']})")
                    new_u = st.text_input("URL貼付", value=item.get("manual_url", ""), key=f"inp_{item['code']}")
                    if new_u != item.get("manual_url"):
                        item["manual_url"] = new_u
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
                    st.write("---")
