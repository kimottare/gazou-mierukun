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
    /* ダークモード対策：印刷時は強制的に白背景・黒文字 */
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
    """スマホ転送用のデータを一時保持するキャッシュ"""
    return {}

shared_store = get_shared_store()

# ==========================================
# 3. 画像取得ロジック (Rakuten -> Bing -> Yahoo)
# ==========================================
def get_best_image(article_num):
    """品番を元に複数のエンジンから画像を検索する"""
    if not article_num or pd.isna(article_num):
        return None
    
    search_query = f"{article_num}"
    
    # 1. 楽天API風検索（簡易スクレイピング例）
    try:
        url = f"https://search.rakuten.co.jp/search/mall/{search_query}/"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        img = soup.find("img")
        if img and 'src' in img.attrs and "https" in img['src']:
            return img['src']
    except:
        pass

    # 2. Bing Search (スクレイピング)
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
    # URLパラメータ(sid)の確認（スマホ閲覧用）
    query_params = st.query_params
    if "sid" in query_params:
        show_mobile_view(query_params["sid"])
        return

    st.title("📦 商品画像見える君 (Delivery Catalog)")
    st.info("納品リスト(Excel/CSV)を読み込み、画像付きカタログを生成します。")

    # サイドバー設定
    with st.sidebar:
        st.header("⚙️ 取得設定")
        concurrency = st.slider("並列処理数 (1-10)", 1, 10, 5)
        is_print_mode = st.toggle("🖨️ 印刷モード（UIを隠す）", False)
        
        st.divider()
        st.write("VMD Team: Sato Shuta")

    # ファイルアップロード
    uploaded_file = st.file_uploader("納品予定リストをアップロード (.xlsx, .csv)", type=["xlsx", "csv"])

    if uploaded_file:
        # データの読み込み（自動エンコーディング/形式判定）
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except:
                df = pd.read_csv(uploaded_file, encoding='shift-jis')
        else:
            df = pd.read_excel(uploaded_file)

        # 列割り当て画面（st.expanderでコンパクトに）
        with st.expander("🔍 列の割り当て設定", expanded=True):
            cols = df.columns.tolist()
            col_art = st.selectbox("品番(Article)列", cols, index=0 if "品番" in cols or "Article" in cols else 0)
            col_bs = st.selectbox("カテゴリー(BS)列", ["なし"] + cols)
            col_stock = st.selectbox("在庫状況/新規列", ["なし"] + cols)

        # 絞り込みフィルター
        st.subheader("🛠️ リストの絞り込み")
        filtered_df = df.copy()
        
        col1, col2 = st.columns(2)
        with col1:
            if col_bs != "なし":
                bs_list = df[col_bs].unique().tolist()
                selected_bs = st.multiselect("カテゴリー(BS)で絞り込み", bs_list, default=bs_list)
                filtered_df = filtered_df[filtered_df[col_bs].isin(selected_bs)]
        
        with col2:
            if col_stock != "なし":
                stock_list = df[col_stock].unique().tolist()
                selected_stock = st.multiselect("在庫状況で絞り込み", stock_list, default=stock_list)
                filtered_df = filtered_df[filtered_df[col_stock].isin(selected_stock)]

        st.write(f"現在の表示件数: **{len(filtered_df)}** 件")

        # 画像取得実行ボタン
        if st.button("🖼️ カタログを生成する"):
            articles = filtered_df[col_art].tolist()
            
            with st.spinner("画像を検索中..."):
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    image_urls = list(executor.map(get_best_image, articles))
                
                filtered_df["image_url"] = image_urls
                st.session_state["catalog_data"] = filtered_df
                st.success("カタログの生成が完了しました！")

        # カタログ表示
        if "catalog_data" in st.session_state:
            display_catalog(st.session_state["catalog_data"], col_art, col_bs, is_print_mode)
            
            # スマホ転送用QRコード発行
            st.divider()
            st.subheader("📱 スマホ（iPhone）へ送る")
            if st.button("スマホ転送用QRコードを発行"):
                sid = str(uuid.uuid4())
                shared_store[sid] = st.session_state["catalog_data"]
                
                # 現在のURLを取得してパラメータを付与
                share_url = f"https://{st.query_params.get('host', 'localhost')}/?sid={sid}"
                # 簡易的なQRコード生成（Streamlit Cloud環境を想定）
                img_qr = qrcode.make(share_url)
                buf = BytesIO()
                img_qr.save(buf, format="PNG")
                
                st.image(buf.getvalue(), caption="iPhoneのEdge（プライベートモード）で読み取ってください")
                st.warning("※このURLはPCのセッションが切れると無効になります。お早めにスクリーンショット等で保存してください。")

# ==========================================
# 5. UI表示用サブ関数
# ==========================================
def display_catalog(df, col_art, col_bs, is_print_mode):
    """カタログをグリッド形式で表示"""
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
                
                # 品番とカテゴリーを表示
                st.caption(f"**{row[col_art]}**")
                if col_bs != "なし":
                    st.write(f"Size/BS: {row[col_bs]}")

def show_mobile_view(sid):
    """スマホ閲覧専用画面"""
    st.title("📱 共有されたカタログ")
    if sid in shared_store:
        df = shared_store[sid]
        st.write(f"共有件数: {len(df)} 件")
        # モバイルではシンプルに表示（品番列などは仮に0,1番目を想定するか、共有データに持たせる）
        # ※ここでは簡易的に全件表示
        for _, row in df.iterrows():
            st.divider()
            if row["image_url"]:
                st.image(row["image_url"], use_container_width=True)
            st.subheader(f"Article: {row.iloc[0]}") # 最初の列を品番と見なす
    else:
        st.error("セッションが切れたか、データが見つかりません。PC側でQRコードを再発行してください。")
        if st.button("トップへ戻る"):
            st.query_params.clear()
            st.rerun()

if __name__ == "__main__":
    main()
