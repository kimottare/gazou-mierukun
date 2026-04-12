import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import uuid
import qrcode
from io import BytesIO
import time

# ==========================================
# 1. ページ設定・セキュリティCSS（ヘッダー非表示）
# ==========================================
st.set_page_config(page_title="商品画像見える君", layout="wide")

# ヘッダー（GitHub/Editアイコン）、フッター、および印刷用CSS
hide_style = """
<style>
/* 画面右上のツールバー（GitHubアイコン、Editボタン等）を非表示 */
header {visibility: hidden;}

/* 画面下部のStreamlitロゴを非表示 */
footer {visibility: hidden;}

/* 印刷用設定: Ctrl+P実行時に不要なUIを隠し、背景を白にする */
@media print {
    header, footer, .stSidebar, .stButton, .stDownloadButton, 
    [data-testid="stExpander"], .stCheckbox, .stTabs, [data-testid="stForm"] {
        display: none !important;
    }
    .main .block-container {
        padding: 0 !important;
        margin: 0 !important;
    }
    body {
        background-color: white !important;
        color: black !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: white !important;
        color: black !important;
    }
}
</style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# ==========================================
# 2. データ共有用データストア (@st.cache_resource)
# ==========================================
@st.cache_resource
def get_shared_store():
    return {}

shared_store = get_shared_store()

# ==========================================
# 3. 画像取得ロジック
# ==========================================
def get_best_image(article_num):
    if not article_num or pd.isna(article_num):
        return None
    
    search_query = f"{article_num}"
    
    # 楽天
    try:
        url = f"https://search.rakuten.co.jp/search/mall/{search_query}/"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        img = soup.find("img")
        if img and 'src' in img.attrs and "https" in img['src']:
            return img['src']
    except:
        pass

    # Bing
    try:
        url = f"https://www.bing.com/images/search?q={search_query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        img = soup.find("img", class_="mimg")
        if img and 'src' in img.attrs:
            return img['src']
    except:
        pass

    return None

# ==========================================
# 4. メインロジック
# ==========================================
def main():
    query_params = st.query_params
    if "sid" in query_params:
        show_mobile_view(query_params["sid"])
        return

    st.title("📦 商品画像見える君")
    st.info("納品リストを読み込み、画像付きカタログを生成します。")

    with st.sidebar:
        st.header("⚙️ 取得設定")
        concurrency = st.slider("並列処理数 (1-10)", 1, 10, 5)
        is_print_mode = st.toggle("🖨️ 印刷モード（UIを隠す）", False)
        st.divider()
        st.write("VMD Team: Sato Shuta")

    uploaded_file = st.file_uploader("納品予定リストをアップロード (.xlsx, .csv)", type=["xlsx", "csv"])

    if uploaded_file:
        # データの読み込み
        if uploaded_file.name.endswith('.csv'):
            try:
                df_raw = pd.read_csv(uploaded_file, encoding='utf-8-sig', header=None)
            except:
                df_raw = pd.read_csv(uploaded_file, encoding='shift-jis', header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        # 【修正】ヘッダー自動検知ロジック
        # 「品番」や「Article」という文字が含まれる最初の行を探す
        header_row_idx = 0
        for i in range(min(len(df_raw), 20)):
            row_values = df_raw.iloc[i].astype(str).tolist()
            if any("品番" in val or "Article" in val or "品名" in val for val in row_values):
                header_row_idx = i
                break
        
        # 検知した行をヘッダーとして設定
        df = df_raw.iloc[header_row_idx+1:].copy()
        df.columns = df_raw.iloc[header_row_idx].tolist()
        df = df.reset_index(drop=True)
        # カラム名から改行コードなどを除去し、Unnamedを防止
        df.columns = [str(c).strip() if pd.notna(c) else f"Unnamed_{i}" for i, c in enumerate(df.columns)]

        # 列割り当て画面（2列レイアウトを維持）
        with st.expander("🔍 列の割り当て設定 (全6項目)", expanded=True):
            cols = df.columns.tolist()
            c1, c2 = st.columns(2)
            
            with c1:
                col_art = st.selectbox("1. 品番(Article)列", cols, index=0 if any("品番" in str(x) for x in cols) else 0)
                col_size = st.selectbox("2. サイズ(Size)列", ["なし"] + cols)
                col_bs = st.selectbox("3. カテゴリー(BS)列", ["なし"] + cols)
            
            with c2:
                col_name = st.selectbox("4. 商品名(Product Name)列", ["なし"] + cols)
                col_qty = st.selectbox("5. 入荷数量列", ["なし"] + cols) # カラーから変更
                col_stock = st.selectbox("6. 在庫状況/新規列", ["なし"] + cols)

        st.subheader("🛠️ リストの絞り込み")
        filtered_df = df.copy()
        fc1, fc2 = st.columns(2)
        with fc1:
            if col_bs != "なし":
                bs_list = df[col_bs].dropna().unique().tolist()
                selected_bs = st.multiselect("カテゴリー(BS)で絞り込み", bs_list, default=bs_list)
                filtered_df = filtered_df[filtered_df[col_bs].isin(selected_bs)]
        with fc2:
            if col_stock != "なし":
                stock_list = df[col_stock].dropna().unique().tolist()
                selected_stock = st.multiselect("在庫状況で絞り込み", stock_list, default=stock_list)
                filtered_df = filtered_df[filtered_df[col_stock].isin(selected_stock)]

        st.write(f"現在の表示件数: **{len(filtered_df)}** 件")

        if st.button("🖼️ カタログを生成する"):
            articles = filtered_df[col_art].tolist()
            with st.spinner("画像を検索中..."):
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    image_urls = list(executor.map(get_best_image, articles))
                filtered_df["image_url"] = image_urls
                st.session_state["catalog_data"] = filtered_df
                st.success("カタログの生成が完了しました！")

        if "catalog_data" in st.session_state:
            display_catalog(
                st.session_state["catalog_data"], 
                col_art, col_size, col_bs, col_name, col_qty, col_stock, 
                is_print_mode
            )
            
            st.divider()
            st.subheader("📱 スマホ（iPhone）へ送る")
            if st.button("スマホ転送用QRコードを発行"):
                sid = str(uuid.uuid4())
                shared_store[sid] = {
                    "df": st.session_state["catalog_data"],
                    "col_art": col_art,
                    "col_size": col_size,
                    "col_bs": col_bs,
                    "col_name": col_name,
                    "col_qty": col_qty,
                    "col_stock": col_stock
                }
                share_url = f"https://{st.query_params.get('host', 'localhost')}/?sid={sid}"
                img_qr = qrcode.make(share_url)
                buf = BytesIO()
                img_qr.save(buf, format="PNG")
                st.image(buf.getvalue(), caption="iPhoneのEdgeで読み取ってください")

# ==========================================
# 5. UI表示用サブ関数
# ==========================================
def display_catalog(df, col_art, col_size, col_bs, col_name, col_qty, col_stock, is_print_mode):
    cols_per_row = 4 if not is_print_mode else 6
    rows = [df[i:i + cols_per_row] for i in range(0, len(df), cols_per_row)]
    
    for row_df in rows:
        cols = st.columns(cols_per_row)
        for i, (idx, row) in enumerate(row_df.iterrows()):
            with cols[i]:
                if row["image_url"]:
                    st.image(row["image_url"], use_container_width=True)
                else:
                    st.warning("No Image")
                
                st.markdown(f"**{row[col_art]}**")
                if col_name != "なし": st.caption(f"{row[col_name]}")
                
                details = []
                if col_qty != "なし": details.append(f"Qty: {row[col_qty]}") # 数量を表示
                if col_size != "なし": details.append(f"Size: {row[col_size]}")
                if col_bs != "なし": details.append(f"BS: {row[col_bs]}")
                if col_stock != "なし": details.append(f"State: {row[col_stock]}")
                
                if details:
                    st.write(" / ".join(details))

def show_mobile_view(sid):
    st.title("📱 納品カタログ")
    if sid in shared_store:
        data = shared_store[sid]
        df = data["df"]
        col_art = data["col_art"]
        col_size = data["col_size"]
        col_bs = data["col_bs"]
        col_name = data["col_name"]
        col_qty = data["col_qty"]
        col_stock = data["col_stock"]

        st.write(f"表示件数: {len(df)} 件")
        for _, row in df.iterrows():
            st.divider()
            if row["image_url"]:
                st.image(row["image_url"], use_container_width=True)
            st.subheader(f"品番: {row[col_art]}")
            if col_name != "なし": st.write(f"**品名:** {row[col_name]}")
            if col_qty != "なし": st.write(f"**入荷数量:** {row[col_qty]}")
            if col_size != "なし": st.write(f"**サイズ:** {row[col_size]}")
            if col_bs != "なし": st.write(f"**カテゴリー:** {row[col_bs]}")
            if col_stock != "なし": st.write(f"**在庫状況:** {row[col_stock]}")
    else:
        st.error("データが見つかりません。PCで再発行してください。")

if __name__ == "__main__":
    main()
