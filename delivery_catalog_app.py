import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json
import os
import concurrent.futures

# --- 🌟 設定 ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217"
AUTO_SAVE_FILE = "auto_save_catalog.json"

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

    /* 画像をハッキリ表示 */
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

    /* Streamlit標準パーツの隠蔽 */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}

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

        /* 各カラム要素を確実に50%幅で固定する（100%への拡大を阻止） */
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
            height: 150px !important; /* スマホ2列時に適切なアスペクト比を維持 */
        }
    }

    /* 4. 印刷用設定（★佐藤さんのご要望を反映：クッキリ化） */
    @media print {
        /* 印刷不要な要素を隠す */
        header, [data-testid="stSidebar"], [data-testid="stToolbar"], 
        .stButton, .stDownloadButton, [data-testid="stExpander"],
        [data-testid="stMultiSelect"], [data-testid="stCheckbox"], 
        .no-print, iframe, .stTextInput, .stAlert, hr {
            display: none !important;
        }
        
        /* ページの余白をなくす */
        .main .block-container {
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        
        /* 文字色を黒に、シャドウをなしに強制する（白背景でハッキリ読めるように） */
        .product-title {
            color: #000 !important;
            text-shadow: none !important;
        }
        
        .product-details {
            color: #000 !important;
            text-shadow: none !important;
        }
        
        /* 画像フィルターを解除し、境界線を濃くする（元の濃さでハッキリ見えるように） */
        .product-image-container {
            border: 1px solid #aaa !important; /* 少し濃い灰色に */
            box-shadow: none !important;
        }
        
        .product-image-container img {
            filter: none !important; /* 印刷時は明るさ調整などのフィルターをかけない */
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 削除確認ダイアログ
# ==========================================
@st.dialog("データの全消去")
def confirm_reset():
    st.warning("現在表示されているリストと保存データをすべて削除します。よろしいですか？")
    if st.button("はい、削除します"):
        # セッションとファイルを削除
        st.session_state.clear()
        if os.path.exists(AUTO_SAVE_FILE):
            os.remove(AUTO_SAVE_FILE)
        st.rerun()

# --- 🔍 検索ロジック ---
def scrape_bing_high_res_image(query, code):
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 画像URLを取得
        for a in soup.find_all('a', class_='iusc'):
            m = a.get('m')
            if m:
                murl = json.loads(m).get('murl')
                # 品番が含まれているか確認
                if murl and str(code).strip() in murl:
                    return murl
    except: pass
    return None

def get_rakuten_image(code):
    if not RAKUTEN_APP_ID: return None
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": RAKUTEN_APP_ID, "keyword": f"adidas {code}", "hits": 3, "imageFlag": 1}
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            items = res.json().get("Items", [])
            for item in items:
                img_url = item["Item"]["mediumImageUrls"][0]["imageUrl"].split("?_ex=")[0]
                return img_url
    except: pass
    return None

def get_best_image(code, name=""):
    rak_url = get_rakuten_image(code)
    if rak_url: return rak_url
    
    query = f"adidas {name} {code}".strip()
    bing_url = scrape_bing_high_res_image(query, code)
    if bing_url: return bing_url
    
    return None

def guess_column_index(columns, keywords, default_idx=0):
    for keyword in keywords:
        for idx, col in enumerate(columns):
            if keyword in str(col).lower(): return idx
    return default_idx

def save_auto_save_data(items):
    with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ==========================================
# メイン UI 
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

# セッション状態の初期化
if "catalog_items" not in st.session_state:
    st.session_state.catalog_items = []
    # 自動保存ファイルがあれば読み込む
    if os.path.exists(AUTO_SAVE_FILE):
        try:
            with open(AUTO_SAVE_FILE, "r", encoding="utf-8") as f:
                st.session_state.catalog_items = json.load(f)
        except: pass

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定・管理")
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    
    # リセットボタン
    if st.button("🗑️ データリセット", use_container_width=True): confirm_reset()
    
    # 印刷ボタン
    if st.button("🖨️ カタログを印刷", use_container_width=True, type="primary"):
        st.write('<script>window.print();</script>', unsafe_allow_html=True)
    
    st.write("---")
    
    # 絞り込みセクション
    st.subheader("🎯 絞り込み")
    # BS(カテゴリー)で絞り込み
    items = st.session_state.catalog_items
    unique_bs = sorted(list(set([i["bs"] for i in items])))
    sel_bs = st.multiselect("BSで絞り込み", unique_bs, default=unique_bs)
    
    st.write("---")

# データが生成されている場合の表示
if st.session_state.catalog_items:
    # 絞り込み適用
    filtered_items = [i for i in st.session_state.catalog_items if i["bs"] in sel_bs]
    
    # ヘッダー情報の表示
    if not filtered_items:
        st.warning("表示するデータがありません。絞り込み設定を確認してください。")
    else:
        # 品番数と合計数量を計算
        art_count = len(filtered_items)
        # 数量を数値に変換して合計 (Qty: 25点 / nan)
        def parse_qty(qty_str):
            try: return float(qty_str.replace('点', '').replace(' ', ''))
            except: return 0.0
        total_qty = sum([parse_qty(i["qty"]) for i in filtered_items])
        st.info(f"📊 **{art_count}** 品番 / 合計 **{int(total_qty)}** 点 を表示中")

        # グリッド表示 (3列)
        for i in range(0, len(filtered_items), 3):
            cols = st.columns(3) 
            for j, item in enumerate(filtered_items[i:i+3]):
                with cols[j]:
                    # 商品名 (文字化け対策)
                    st.markdown(f'<div class="product-title">{item["name"]}</div>', unsafe_allow_html=True)
                    # 詳細情報
                    st.markdown(f'<div class="product-details">Art: {item["code"]}<br>Size: {item["size"]}<br>Qty: {item["qty"]}</div>', unsafe_allow_html=True)
                    # 画像
                    if item["manual_url"]:
                        st.markdown(f'<div class="product-image-container"><img src="{item["manual_url"]}"></div>', unsafe_allow_html=True)
                    elif item["auto_url"]:
                        st.markdown(f'<div class="product-image-container"><img src="{item["auto_url"]}"></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="product-image-container"><div style="color:#999; font-size:0.8rem;">画像なし</div></div>', unsafe_allow_html=True)
                    
                    # Google画像検索リンク (品番をクエリに)
                    st.markdown(f"🔍 [Google画像検索](https://www.google.com/search?tbm=isch&q=adidas+{item['code']})")
                    # URL手動貼り付け
                    new_url = st.text_input("URLを手動貼り付け", value=item["manual_url"], key=f"inp_{item['code']}")
                    # URLが変更されたら保存
                    if new_url != item["manual_url"]:
                        item["manual_url"] = new_url
                        save_auto_save_data(st.session_state.catalog_items)
                        st.rerun()

# データ入力セクション
else:
    st.subheader("📝 新規リストを作成")
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                # 文字コードが特定できない場合はエラー
                try: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str)
                except: df = pd.read_csv(uploaded_file, na_filter=False, dtype=str, encoding='cp932')
            else:
                df = pd.read_excel(uploaded_file, na_filter=False, dtype=str)
            
            # データフレームの調整
            # 品番、商品名、BS、サイズ、数量、ステータス、店舗名称の列を特定
            columns = df.columns.tolist()
            
            # 列の自動紐付け確認
            with st.expander("📋 列割り当て確認"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    code_col = st.selectbox("Article (品番)", columns, index=guess_column_index(columns, ['artno', 'article', 'art', 'code']))
                    size_col = st.selectbox("Size (サイズ)", columns, index=guess_column_index(columns, ['size', 'サイズ']))
                with c2:
                    name_col = st.selectbox("Name (商品名)", columns, index=guess_column_index(columns, ['商品名称', '名称', 'name', 'item']))
                    qty_col = st.selectbox("Qty (数量)", columns, index=guess_column_index(columns, ['qty', '数量']))
                with c3:
                    # image_3.png の修正を反映
                    bs_col = st.selectbox("BS (カテゴリー)", columns, index=guess_column_index(columns, ['bs', 'カテゴリー', 'department']))
                    status_col = st.selectbox("Status (ステータス)", columns, index=guess_column_index(columns, ['status', 'ステータス']))
            
            if st.button("カタログ作成開始", type="primary"):
                results = []
                # 重複のない品番リスト
                unique_codes = df[code_col].unique()
                unique_codes = [c for c in unique_codes if c and str(c).lower() != 'nan']
                
                # 並行処理で画像検索
                p_bar = st.progress(0)
                def fetch_data(i, code):
                    row = df[df[code_col] == code].iloc[0]
                    # 商品名 (文字化け対策: UTF-8でエンコード)
                    name_raw = row[name_col]
                    name = name_raw.encode('latin1').decode('utf-8') if '\\u' in name_raw else name_raw

                    # Qty: 25点 / nan
                    raw_inv = row[qty_col]
                    raw_qty = row['在庫']
                    inv_qty = parse_qty(raw_inv)
                    qty = parse_qty(raw_qty)
                    # ステータス情報も付記
                    status = row[status_col]
                    qty_str = f"{int(inv_qty)}点 / {int(qty)}点 ({status})"
                    
                    # 画像取得
                    url = get_best_image(code, name)
                    return i, {"code": code, "name": name, "bs": row[bs_col], "size": row[size_col], "qty": qty_str, "auto_url": url, "source": "自動検索", "manual_url": ""}
                
                # 品番ごとにデータを集約して並行検索
                p_bar.write(f"自動検索中... ({len(unique_codes)}件)")
                unsorted_results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
                    futures = [exe.submit(fetch_data, i, code) for i, code in enumerate(unique_codes)]
                    for i, f in enumerate(concurrent.futures.as_completed(futures)):
                        idx, res = f.result()
                        unsorted_results.append((idx, res))
                        p_bar.progress((i + 1) / len(unique_codes))
                
                # 元の順番に並べ替え
                unsorted_results.sort(key=lambda x: x[0])
                results = [item for idx, item in unsorted_results]

                # セッションと自動保存
                st.session_state.catalog_items = results
                save_auto_save_data(results)
                st.rerun()

        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました。エラー: {e}")
