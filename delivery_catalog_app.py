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

# --- 🌟 楽天アプリID ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

st.set_page_config(page_title="商品画像見える君", layout="wide")

# 👇 印刷時(Ctrl+P)に不要なエリアを消すための設定を追加しました
st.markdown("""
    <style>
    @media print {
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], .stButton, .stDownloadButton, [data-testid="stExpander"],
        [data-testid="stMultiSelect"], [data-testid="stCheckbox"], iframe, .no-print {
            display: none !important;
        }
        .main .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
        }
        /* 👇ここから追加：背景を強制的に白、文字を黒にする */
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
    html_content += f"""
        </div>
        <div class="footer">作成日時: {now_str}</div>
    </body>
    </html>
    """
    return html_content

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "localhost"

def is_valid_adidas_img(url):
    keywords = ["adidas", "yimg", "bing", "gstatic", "shop-adidas", "mm-adidas"]
    return any(k in url.lower() for k in keywords)

def scrape_bing_high_res_image(query, code):
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', class_='iusc'):
            m_str = a.get('m')
            if m_str:
                try:
                    m_data = json.loads(m_str)
                    murl = m_data.get('murl')
                    if murl:
                        if str(code).strip().lower() in murl.lower() and is_valid_adidas_img(murl):
                            return murl, True
                except: continue
    except: pass
    return None, False

def scrape_yahoo_image(query, code):
    url = f"https://search.yahoo.co.jp/image/search?p={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith("http"):
                if "logo" not in src.lower() and "icon" not in src.lower():
                    if str(code).strip().lower() in src.lower() and is_valid_adidas_img(src):
                        return src, True
    except: pass
    return None, False

def get_rakuten_image(code):
    if not RAKUTEN_APP_ID: return None, False
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 3, "imageFlag": 1}
    fallback_url = None
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                item_data = item["Item"]
                if "mediumImageUrls" in item_data and len(item_data["mediumImageUrls"]) > 0:
                    img_url = item_data["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                    item_name = item_data.get("itemName", "").lower()
                    if str(code).strip().lower() in item_name:
                        return img_url, True
                    if not fallback_url:
                        fallback_url = img_url
    except: pass
    return fallback_url, False

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    query = f"adidas {name} {code_str}".strip()
    rakuten_url, rakuten_exact = get_rakuten_image(code_str)
    if rakuten_exact: return {"url": rakuten_url, "source": "楽天公式 (高精度)"}
    bing_url, bing_exact = scrape_bing_high_res_image(query, code_str)
    if bing_exact: return {"url": bing_url, "source": "Web検索 (高画質・高精度)"}
    yahoo_url, yahoo_exact = scrape_yahoo_image(query, code_str)
    if yahoo_exact: return {"url": yahoo_url, "source": "Yahoo!検索 (高精度)"}
    if rakuten_url: return {"url": rakuten_url, "source": "楽天公式 (推測・近似色など)"}
    return None

def guess_column_index(columns, keywords, default_idx=0):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            if keyword == str(col).lower(): return idx
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
    if os.path.exists(AUTO_SAVE_FILE):
        try:
            with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
                st.session_state.catalog_items = json.load(f)
                st.session_state.generated = True
        except:
            st.session_state.catalog_items = []
            st.session_state.generated = False
    else:
        st.session_state.catalog_items = []
        st.session_state.generated = False

with st.sidebar:
    st.header("⚙️ 設定・管理")
    is_print_mode = st.toggle("印刷用コンパクト表示モード", help="URL入力やリンクを隠し、画像を小さくして紙を節約します。")
    
    st.write("---")
    st.subheader("💾 データの書き出し")
    if st.session_state.generated:
        json_string = json.dumps(st.session_state.catalog_items, ensure_ascii=False, indent=2)
        st.download_button(label="このPCの作業データを保存 (.json)", data=json_string, file_name="catalog_backup.json", mime="application/json", use_container_width=True)
    else:
        st.caption("リスト作成後に保存できます。")

    st.write("---")
    st.subheader("📂 データの復元")
    backup_file = st.file_uploader("保存ファイルを読み込む", type=['json'], key="restore_uploader")
    if backup_file:
        if st.button("このファイルで復元する", use_container_width=True):
            try:
                loaded_items = json.load(backup_file)
                st.session_state.catalog_items = loaded_items
                st.session_state.generated = True
                save_auto_save_data(loaded_items)
                st.rerun()
            except: st.error("正しいバックアップファイルではありません。")

    st.write("---")
    if st.session_state.generated:
        if st.button("🗑️ データを全消去してリセット", type="primary", use_container_width=True):
            st.session_state.generated = False
            st.session_state.catalog_items = []
            if os.path.exists(AUTO_SAVE_FILE): os.remove(AUTO_SAVE_FILE)
            st.rerun()

if not st.session_state.generated:
    st.subheader("📝 新しいリストから作成")
    uploaded_file = st.file_uploader("ExcelまたはCSVファイルをアップロード", type=['xlsx', 'xlsm', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                try:
                    df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, header=None, encoding='cp932')
            else:
                df = pd.read_excel(uploaded_file, na_filter=False, dtype=str, header=None)
            
            header_idx = 0
            for i, row in df.iterrows():
                valid_count = sum(1 for val in row if str(val).strip() != "" and str(val).lower() != "nan" and str(val) != "None")
                if valid_count >= 3: 
                    header_idx = i
                    break
            
            df.columns = df.iloc[header_idx].tolist()
            df = df.iloc[header_idx+1:].reset_index(drop=True)
            
            columns = []
            for i, col in enumerate(df.columns):
                col_str = str(col).strip()
                if col_str == "" or col_str.lower() == "nan" or col_str.startswith("Unnamed") or col_str == "None":
                    new_col = f"列{i+1}(見出しなし)"
                else:
                    new_col = col_str
                while new_col in columns:
                    new_col += "*"
                columns.append(new_col)
            df.columns = columns
            
            with st.expander("📋 読み込む列の割り当て (クリックして確認・変更)"):
                sel_col1, sel_col2, sel_col3 = st.columns(3)
                
                with sel_col1:
                    code_col = st.selectbox("Articleの列", columns, index=guess_column_index(columns, ['artno', 'article', 'art', 'code']))
                    size_col_idx = guess_column_index(columns, ['size', 'サイズ', 'sizetext'])
                    size_col = st.selectbox("サイズ(Size)の列", ["(なし)"] + columns, index=size_col_idx+1)
                    
                with sel_col2:
                    name_col = st.selectbox("Nameの列", columns, index=guess_column_index(columns, ['商品名称', 'name', 'item']))
                    qty_col_idx = guess_column_index(columns, ['qty', 'quantity', '数量', '出荷数量'])
                    qty_col = st.selectbox("数量(Qty)の列", ["(なし)"] + columns, index=qty_col_idx+1)
                    
                with sel_col3:
                    bs_col_idx = guess_column_index(columns, ['bs', 'category'])
                    bs_col = st.selectbox("BSの列", ["(なし)"] + columns, index=bs_col_idx+1)
                    status_col = st.selectbox("Status(在庫状況)の列", ["(なし)"] + columns, index=len(columns))
            
            if st.button("作成", type="primary", use_container_width=True):
                display_df = df[df[code_col].astype(str).str.strip() != ""]
                
                # --- 追加：サイズと数量の集計処理 ---
                aggregated_sizes = {}
                aggregated_qtys = {}
                
                for code, group in display_df.groupby(code_col):
                    code_str = str(code).strip()
                    size_dict = {}
                    total_qty = 0
                    
                    for _, row in group.iterrows():
                        s_val = str(row[size_col]).strip() if size_col != "(なし)" else ""
                        q_val = str(row[qty_col]).strip() if qty_col != "(なし)" else ""
                        if s_val.lower() == 'nan': s_val = ""
                        if q_val.lower() == 'nan': q_val = ""
                        
                        q_num = 0
                        try:
                            if q_val: q_num = float(q_val)
                        except: pass
                        
                        total_qty += q_num
                        
                        if s_val:
                            if s_val in size_dict:
                                size_dict[s_val] += q_num
                            else:
                                size_dict[s_val] = q_num
                    
                    size_list = []
                    for s, q in size_dict.items():
                        q_str = str(int(q)) if q == int(q) else str(q)
                        if q > 0:
                            size_list.append(f"{s}({q_str})")
                        else:
                            size_list.append(s)
                            
                    aggregated_sizes[code_str] = ", ".join(size_list)
                    t_q_str = str(int(total_qty)) if total_qty == int(total_qty) else str(total_qty)
                    aggregated_qtys[code_str] = t_q_str if total_qty > 0 else ""

                display_df = display_df.drop_duplicates(subset=[code_col])
                # --- 集計処理ここまで ---
                
                st.info(f"自動検索中... ({len(display_df)}件)")
                p_bar = st.progress(0)
                status_text = st.empty()
                
                def fetch_data(args):
                    idx_num, row = args
                    code, name = str(row[code_col]).strip(), str(row[name_col]).strip()
                    bs_val = str(row[bs_col]).strip() if bs_col != "(なし)" else ""
                    # 個別の行からではなく、集計した辞書から取得するよう変更
                    size_val = aggregated_sizes.get(code, "")
                    qty_val = aggregated_qtys.get(code, "")
                    st_val = str(row[status_col]).strip() if status_col != "(なし)" else ""
                    
                    if not code or code.lower() == 'nan' or code.lower() == 'none': return idx_num, None
                    img_info = get_best_image(code, name)
                    
                    return idx_num, {
                        "code": code, "name": name, "bs": bs_val, "size": size_val, "qty": qty_val, "status": st_val, 
                        "auto_url": img_info["url"] if img_info else None, 
                        "source": img_info["source"] if img_info else None, "manual_url": ""
                    }

                total_count = len(display_df)
                completed_count = 0
                tasks, unsorted_items = [], []
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    for i, (_, row) in enumerate(display_df.iterrows()):
                        tasks.append(executor.submit(fetch_data, (i, row)))
                    for future in concurrent.futures.as_completed(tasks):
                        idx_num, result = future.result()
                        if result: unsorted_items.append((idx_num, result))
                        completed_count += 1
                        p_bar.progress(min(completed_count / total_count, 1.0))
                        status_text.text(f"🚀 高速検索中... {completed_count} / {total_count} 件完了")
                
                unsorted_items.sort(key=lambda x: x[0])
                items = [item for _, item in unsorted_items]
                
                st.session_state.catalog_items = items
                st.session_state.generated = True
                save_auto_save_data(items)
                st.rerun() 
        except Exception as e: st.error(f"エラー: {e}")

if st.session_state.generated:
    items = st.session_state.catalog_items
    filtered_items = items
    
    # 👇 印刷時は非表示にするクラス(no-print)を各テキストに追加しました
    st.markdown("<h3 class='no-print' style='margin-top: 1rem;'>🎯 リストの絞り込み</h3>", unsafe_allow_html=True)
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        unique_bs = sorted(list(set([item["bs"] for item in items if item.get("bs") and str(item["bs"]).lower() != 'nan'])))
        # 👇 プルダウンから、スクロール枠付きのチェックボックスリストに変更
        st.markdown("<p class='no-print' style='font-size:0.9rem; font-weight:bold; margin-bottom:0.5rem;'>カテゴリー(BS)で絞り込む</p>", unsafe_allow_html=True)
        selected_bs = []
        if unique_bs:
            with st.container(height=200):
                for bs in unique_bs:
                    if st.checkbox(bs, key=f"chk_bs_{bs}"):
                        selected_bs.append(bs)
                        
        if selected_bs:
            filtered_items = [item for item in filtered_items if item["bs"] in selected_bs]

    with f_col2:
        is_new_only = st.toggle("✨ 新規入荷（#N/A, #REF!）のみを表示")
        if is_new_only:
            error_vals = ["#N/A", "#REF!", "NAN", "NONE", ""]
            filtered_items = [item for item in filtered_items if str(item["status"]).strip().upper() in error_vals]
        else:
            unique_status = sorted(list(set([item["status"] for item in items if item.get("status")])))
            # 👇 プルダウンから、スクロール枠付きのチェックボックスリストに変更
            st.markdown("<p class='no-print' style='font-size:0.9rem; font-weight:bold; margin-bottom:0.5rem;'>手動で在庫状況を絞り込む</p>", unsafe_allow_html=True)
            selected_status = []
            if unique_status:
                with st.container(height=200):
                    for stat in unique_status:
                        if st.checkbox(stat, key=f"chk_stat_{stat}"):
                            selected_status.append(stat)
                            
            if selected_status:
                filtered_items = [item for item in filtered_items if item["status"] in selected_status]
    
    st.markdown("<hr class='no-print'>", unsafe_allow_html=True)
    
    st.markdown("<h3 class='no-print' style='margin-top: 1rem;'>📱 スマホでカタログを見る</h3>", unsafe_allow_html=True)
    col_dl, col_qr = st.columns([1, 1])
    
    with col_dl:
        st.markdown("<p class='no-print' style='font-weight: bold; margin-bottom: 0.5rem;'>方法1: ファイルとして保存して送る</p>", unsafe_allow_html=True)
        html_string = generate_html_report(filtered_items)
        st.download_button(
            label="『スマホ閲覧用Webページ』として保存", 
            data=html_string, 
            file_name="スマホ閲覧用カタログ.html", 
            mime="text/html", 
            use_container_width=True,
            type="primary"
        )
        st.markdown("<p class='no-print' style='font-size: 0.8rem; color: #666;'>保存されたHTMLファイルを共有フォルダ等経由でスマホに送ります。</p>", unsafe_allow_html=True)
            
    with col_qr:
        st.markdown("<p class='no-print' style='font-weight: bold; margin-bottom: 0.5rem;'>方法2: QRコードを読み取って直接繋ぐ</p>", unsafe_allow_html=True)
        local_ip = get_local_ip()
        app_url = f"http://{local_ip}:8501"
        st.markdown("<p class='no-print' style='font-size: 0.8rem; color: #666;'>※PCとスマホが同じ社内Wi-Fiに繋がっている必要があります。</p>", unsafe_allow_html=True)
        
        qr_html = f"""
        <div style="display: flex; justify-content: left; align-items: center; background: transparent; padding: 5px;">
            <div id="qrcode" style="background: white; padding: 10px; border-radius: 8px; border: 1px solid #ddd; display: inline-block;"></div>
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <script>
            new QRCode(document.getElementById("qrcode"), {{
                text: "{app_url}",
                width: 140,
                height: 140,
                colorDark : "#000000",
                colorLight : "#ffffff",
                correctLevel : QRCode.CorrectLevel.L
            }});
        </script>
        """
        import streamlit.components.v1 as components
        components.html(qr_html, height=180)
        st.markdown("<p class='no-print' style='font-size: 0.8rem; color: #666;'>スマホのカメラで読み取ってください</p>", unsafe_allow_html=True)
    
    st.markdown("<hr class='no-print'>", unsafe_allow_html=True)

    num_cols = 4 if is_print_mode else 3
    img_height = "180px" if is_print_mode else "300px"

    for i in range(0, len(filtered_items), num_cols):
        cols = st.columns(num_cols) 
        for j in range(num_cols):
            index = i + j
            if index < len(filtered_items):
                item = filtered_items[index]
                code, name = item["code"], item["name"]
                with cols[j]:
                    if is_print_mode:
                        st.markdown(f"<p style='font-size:0.9rem; font-weight:bold; margin-bottom:0;'>{name}</p>", unsafe_allow_html=True)
                        size_str = f" / {item.get('size', '')}" if item.get('size') else ""
                        qty_str = f" / {item.get('qty', '')}点" if item.get('qty') else ""
                        st.caption(f"{code}{size_str}{qty_str} / {item.get('status', '')}")
                    else:
                        st.markdown(f"<b><span style='font-size:1.2rem;'>{name}</span></b>", unsafe_allow_html=True)
                        size_str = f" / Size: {item.get('size', '')}" if item.get('size') else ""
                        qty_str = f" / Qty: {item.get('qty', '')}" if item.get('qty') else ""
                        st.caption(f"Art: {code} / BS: {item.get('bs', '')}{size_str}{qty_str} / Status: {item.get('status', '')}")
                    
                    input_key = f"manual_url_{code}"
                    if not is_print_mode:
                        manual_url = st.text_input("URL貼り付け", value=item.get("manual_url", ""), key=input_key)
                        if manual_url != item.get("manual_url"):
                            item["manual_url"] = manual_url 
                            save_auto_save_data(st.session_state.catalog_items)
                        display_url = manual_url if manual_url else item.get("auto_url")
                    else:
                        display_url = item.get("manual_url") if item.get("manual_url") else item.get("auto_url")
                    
                    if display_url:
                        st.markdown(f'<div style="height:{img_height};display:flex;justify-content:center;align-items:center;background:#fff;border-radius:6px;margin-bottom:5px;overflow:hidden;border:1px solid #eee;"><img src="{display_url}" style="max-height:100%;max-width:100%;object-fit:contain;"></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="height:{img_height};display:flex;justify-content:center;align-items:center;background:#f8f9fa;border-radius:6px;margin-bottom:5px;border:1px solid #ddd;font-size:0.8rem;color:#999;">画像なし</div>', unsafe_allow_html=True)
                    
                    if not is_print_mode:
                        st.caption(f"元:{item.get('source','')}")
                        st.markdown(f"🔍 [Google検索](https://www.google.com/search?tbm=isch&q=adidas+{code})")
                        st.write("---")
