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

# --- 🌟 楽天アプリID ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

# 👇 PCとスマホ間でデータを共有するためのメモリ
@st.cache_resource
def get_shared_store():
    return {}

st.set_page_config(page_title="商品画像見える君", layout="wide")

# 👇 CSS: ヘッダー非表示・印刷設定
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}

    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], .stButton, .stDownloadButton, [data-testid="stExpander"],
        [data-testid="stMultiSelect"], [data-testid="stCheckbox"], iframe, .no-print {
            display: none !important;
        }
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
        }
        body, .stApp, .main, .block-container, div[data-testid="stAppViewContainer"] {
            background-color: white !important;
            background-image: none !important;
        }
        p, span, h1, h2, h3, h4, h5, h6, div, label {
            color: black !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 削除確認用ダイアログ
# ==========================================
@st.dialog("データの全消去")
def confirm_reset():
    st.warning("現在表示されているリストと保存データをすべて削除します。よろしいですか？")
    st.write("※この操作は取り消せません。")
    
    col1, col2 = st.columns(2)
    if col1.button("はい、削除します", type="primary", use_container_width=True):
        st.session_state.generated = False
        st.session_state.catalog_items = []
        if os.path.exists(AUTO_SAVE_FILE): 
            os.remove(AUTO_SAVE_FILE)
        st.query_params.clear()
        st.rerun()
    
    if col2.button("いいえ、戻ります", use_container_width=True):
        st.rerun()

# ==========================================
# ロジック・ヘルパー関数
# ==========================================
def generate_html_report(items):
    now_str = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>入荷予定カタログ</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; padding: 10px; margin: 0; }}
            h1 {{ text-align: center; color: #1a1a1a; font-size: 1.3rem; margin: 10px 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #333; }}
            .grid-container {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
            @media (min-width: 600px) {{ .grid-container {{ grid-template-columns: repeat(3, 1fr); }} }}
            @media (min-width: 900px) {{ .grid-container {{ grid-template-columns: repeat(4, 1fr); }} }}
            .card {{ background: #fff; border-radius: 12px; padding: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); display: flex; flex-direction: column; }}
            .img-container {{ height: 140px; display: flex; justify-content: center; align-items: center; overflow: hidden; margin-bottom: 8px; }}
            .img-container img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
            .no-img {{ height: 140px; display: flex; justify-content: center; align-items: center; background: #f8f9fa; color: #adb5bd; border-radius: 8px; margin-bottom: 8px; font-size: 0.8rem; border: 1px dashed #dee2e6; }}
            .title {{ font-weight: 700; font-size: 0.85rem; margin: 0 0 4px 0; color: #212529; line-height: 1.2; word-break: break-all; }}
            .details {{ font-size: 0.7rem; color: #6c757d; margin: 0; line-height: 1.4; }}
            .status {{ display: inline-block; background: #ffe3e3; color: #c92a2a; padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 0.65rem; margin-top: 6px; align-self: flex-start; }}
            .footer {{ text-align: center; font-size: 0.7rem; color: #888; margin-top: 20px; padding-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>📦 商品カタログ ({len(items)}件)</h1>
        <div class="grid-container">
    """
    for item in items:
        img_url = item.get("manual_url") if item.get("manual_url") else item.get("auto_url")
        img_html = f'<div class="img-container"><img src="{img_url}" loading="lazy"></div>' if img_url else '<div class="no-img">画像なし</div>'
        status = item.get("status", "")
        status_html = f'<div class="status">{status}</div>' if status else ""
        size_str = f" / Size: {item.get('size', '')}" if item.get('size') else ""
        qty_str = f" / Qty: {item.get('qty', '')}" if item.get('qty') else ""
        html_content += f"""
            <div class="card">
                {img_html}
                <p class="title">{item.get("name", "")}</p>
                <p class="details">Art: {item.get("code", "")}<br>BS: {item.get("bs", "")}{size_str}{qty_str}</p>
                {status_html}
            </div>
        """
    html_content += f"</div><div class='footer'>作成日時: {now_str}</div></body></html>"
    return html_content

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
                m_data = json.loads(m_str)
                murl = m_data.get('murl')
                if murl and str(code).strip().lower() in murl.lower() and is_valid_adidas_img(murl):
                    return murl, True
    except: pass
    return None, False

def scrape_yahoo_image(query, code):
    url = f"https://search.yahoo.co.jp/image/search?p={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith("http") and str(code).strip().lower() in src.lower() and is_valid_adidas_img(src):
                return src, True
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
                item_data = item["Item"]
                if "mediumImageUrls" in item_data and len(item_data["mediumImageUrls"]) > 0:
                    img_url = item_data["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                    if str(code).strip().lower() in item_data.get("itemName", "").lower():
                        return img_url, True
    except: pass
    return None, False

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    rakuten_url, rakuten_exact = get_rakuten_image(code_str)
    if rakuten_exact: return {"url": rakuten_url, "source": "楽天公式"}
    bing_url, bing_exact = scrape_bing_high_res_image(query, code_str)
    if bing_exact: return {"url": bing_url, "source": "Bing検索"}
    yahoo_url, yahoo_exact = scrape_yahoo_image(query, code_str)
    if yahoo_exact: return {"url": yahoo_url, "source": "Yahoo検索"}
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
st.title("📦 商品画像見える君")

if "generated" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = False
    if "sid" in st.query_params:
        try:
            sid = st.query_params["sid"]
            store = get_shared_store()
            if sid in store:
                st.session_state.catalog_items = store[sid]
                st.session_state.generated = True
                st.success("✅ スマホへ転送完了")
        except: pass
    elif os.path.exists(AUTO_SAVE_FILE):
        try:
            with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
                st.session_state.catalog_items = json.load(f)
                st.session_state.generated = True
        except: pass

with st.sidebar:
    st.header("⚙️ 設定・管理")
    concurrency = st.slider("⚡ 画像取得スピード", 1, 10, 3)
    is_print_mode = st.toggle("印刷用コンパクト表示モード")
    st.write("---")
    if st.session_state.generated:
        json_string = json.dumps(st.session_state.catalog_items, ensure_ascii=False, indent=2)
        st.download_button("データを保存 (.json)", json_string, "catalog_backup.json", "application/json", use_container_width=True)
    
    if st.session_state.generated:
        if st.button("🗑️ リセット", type="primary", use_container_width=True):
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
                if sum(1 for val in row if str(val).strip() != "" and str(val).lower() != "nan") >= 3:
                    header_idx = i
                    break
            df.columns = df.iloc[header_idx].tolist()
            df = df.iloc[header_idx+1:].reset_index(drop=True)
            columns = [str(c).strip() if str(c).strip() and str(c).lower() != 'nan' else f"列{i+1}" for i, c in enumerate(df.columns)]
            df.columns = columns

            with st.expander("📋 読み込む列の割り当て"):
                sel_col1, sel_col2, sel_col3 = st.columns(3)
                with sel_col1:
                    code_col = st.selectbox("Articleの列", columns, index=guess_column_index(columns, ['artno', 'article', 'art', 'code']))
                    size_col = st.selectbox("サイズの列", ["(なし)"] + columns, index=guess_column_index(columns, ['size', 'サイズ'])+1)
                with sel_col2:
                    name_col = st.selectbox("Nameの列", columns, index=guess_column_index(columns, ['商品名称', '名称', 'name', 'item']))
                    qty_col = st.selectbox("数量の列", ["(なし)"] + columns, index=guess_column_index(columns, ['qty', '数量'])+1)
                with sel_col3:
                    bs_col = st.selectbox("BSの列", ["(なし)"] + columns, index=guess_column_index(columns, ['bs', 'category'])+1)
                    status_col = st.selectbox("Statusの列", ["(なし)"] + columns, index=len(columns))

            if st.button("作成", type="primary", use_container_width=True):
                display_df = df[df[code_col].astype(str).str.strip() != ""]
                agg_sizes, agg_qtys = {}, {}
                for code, group in display_df.groupby(code_col):
                    code_str = str(code).strip()
                    size_dict, total_qty = {}, 0
                    for _, row in group.iterrows():
                        s_val = str(row[size_col]).strip() if size_col != "(なし)" else ""
                        q_val = str(row[qty_col]).strip() if qty_col != "(なし)" else "0"
                        try: q_num = float(q_val)
                        except: q_num = 0
                        total_qty += q_num
                        if s_val: size_dict[s_val] = size_dict.get(s_val, 0) + q_num
                    agg_sizes[code_str] = ", ".join([f"{s}({int(q) if q==int(q) else q})" for s, q in size_dict.items()])
                    agg_qtys[code_str] = str(int(total_qty) if total_qty == int(total_qty) else total_qty) if total_qty > 0 else ""

                display_df = display_df.drop_duplicates(subset=[code_col])
                st.info(f"自動検索中... ({len(display_df)}件)")
                p_bar = st.progress(0)
                def fetch_data(args):
                    idx, row = args
                    code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                    if not code or code.lower() in ['nan', 'none']: return idx, None
                    img = get_best_image(code, name)
                    return idx, {"code": code, "name": name, "bs": str(row[bs_col]) if bs_col != "(なし)" else "",
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
    items = st.session_state.catalog_items
    filtered = items
    st.markdown("<h3 class='no-print'>🎯 絞り込み</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    with c1:
        unique_bs = sorted(list(set([i["bs"] for i in items if i.get("bs")])))
        def set_all_bs(state):
            for b in unique_bs: st.session_state[f"chk_{b}"] = state

        btn_col1, btn_col2 = st.columns(2)
        btn_col1.button("全て選択", use_container_width=True, on_click=set_all_bs, args=(True,))
        btn_col2.button("全て解除", use_container_width=True, on_click=set_all_bs, args=(False,))
            
        sel_bs = []
        if unique_bs:
            with st.container(height=150):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}"): sel_bs.append(b)
        if sel_bs: filtered = [i for i in filtered if i["bs"] in sel_bs]
        
    with c2:
        if st.toggle("✨ 新規入荷のみ"):
            filtered = [i for i in filtered if str(i.get("status", "")).strip().upper() in ["#N/A", "#REF!", "NAN", "NONE", "", "NULL"]]
    
    # 👇 ここを追加：表示件数と合計数量のカウンター
    total_q_sum = 0
    for item in filtered:
        try:
            q_val = float(item.get("qty", 0)) if item.get("qty") else 0
            total_q_sum += q_val
        except: pass
    total_q_display = int(total_q_sum) if total_q_sum == int(total_q_sum) else total_q_sum
    
    st.info(f"📦 現在の表示: **{len(filtered)}** 品番 / 合計数量: **{total_q_display}** 点")
    
    st.markdown("<h3 class='no-print'>📱 スマホ転送</h3>", unsafe_allow_html=True)
    cdl, cqr = st.columns(2)
    with cdl: st.download_button("HTML保存", generate_html_report(filtered), "catalog.html", "text/html", use_container_width=True)
    with cqr:
        sid = st.session_state.get("share_id", uuid.uuid4().hex[:8])
        st.session_state.share_id = sid
        get_shared_store()[sid] = filtered
        qr_html = f"""
        <div style="display:flex; justify-content:center; align-items:center;">
            <div id="qrcode" style="background:white;padding:10px;border-radius:8px; display:inline-block;"></div>
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <script>
            var baseUrl = window.parent.location.href.split('?')[0];
            var url = baseUrl + "?sid={sid}";
            new QRCode(document.getElementById("qrcode"), {{text:url, width:128, height:128}});
        </script>
        """
        st.components.v1.html(qr_html, height=160)

    # --- カタログ表示本体 ---
    num_cols = 4 if is_print_mode else 3
    img_h = "160px" if is_print_mode else "280px"
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols) 
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                st.markdown(f"**{item['name']}**")
                st.caption(f"{item['code']} / {item['size']} / {item['qty']}点 / {item['status']}")
                disp_url = item.get("manual_url") if item.get("manual_url") else item.get("auto_url")
                if disp_url: st.markdown(f'<div style="height:{img_h};display:flex;justify-content:center;background:#fff;border-radius:6px;border:1px solid #eee;overflow:hidden;"><img src="{disp_url}" style="max-height:100%;max-width:100%;object-fit:contain;"></div>', unsafe_allow_html=True)
                else: st.markdown(f'<div style="height:{img_h};display:flex;justify-content:center;align-items:center;background:#f8f9fa;border-radius:6px;border:1px solid #ddd;color:#999;">画像なし</div>', unsafe_allow_html=True)
                
                if not is_print_mode:
                    st.markdown(f"🔍 [Google検索](https://www.google.com/search?tbm=isch&q=adidas+{item['code']})")
                    new_url = st.text_input("画像URLを貼り付け", value=item.get("manual_url", ""), key=f"inp_{item['code']}")
                    if new_url != item.get("manual_url"):
                        item["manual_url"] = new_url
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()
                    if item.get('source'): st.caption(f"元:{item['source']}")
                    st.write("---")
