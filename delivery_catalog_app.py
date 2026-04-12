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

# --- 🌟 設定 ---
RAKUTEN_APP_ID = "9fd3dd97-a071-4e2b-8579-dec02ea27217" 
AUTO_SAVE_FILE = "auto_save_catalog.json" 

@st.cache_resource
def get_shared_store():
    return {}

st.set_page_config(page_title="商品画像見える君", layout="wide")

# ==========================================
# 🎨 究極の視認性・モバイル2列「絶対固定」CSS
# ==========================================
st.markdown("""
    <style>
    /* 1. 基本フォント・背景設定（iPhone/Edge対応） */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif;
    }

    .main-title {
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        text-shadow: 3px 3px 12px rgba(0,0,0,1.0), 0 0 20px rgba(0,0,0,0.6) !important;
        border-left: 10px solid #ffffff;
        padding-left: 15px;
        margin: 1rem 0 !important;
    }

    .product-title {
        font-weight: 800;
        font-size: 0.95rem;
        line-height: 1.2;
        height: 2.4em;
        overflow: hidden;
        color: #ffffff !important;
        text-shadow: 2px 2px 6px rgba(0,0,0,1.0) !important;
        margin-bottom: 4px;
    }

    .product-image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid #444;
        overflow: hidden;
        margin-bottom: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }

    .product-image-container img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
    }

    .product-details {
        font-size: 0.75rem;
        color: #ddd !important;
        line-height: 1.3;
        height: 4.0em;
        overflow: hidden;
        text-shadow: 1px 1px 4px rgba(0,0,0,0.8);
    }

    /* ヘッダー・フッターの整理 */
    footer {visibility: hidden;}
    [data-testid="stHeader"] { background: transparent !important; }

    /* ==========================================
       📱 iPhone Safari/Edge用：2列強制命令
       ========================================== */
    @media screen and (max-width: 768px) {
        /* Streamlitの標準カラム挙動を「親要素」から破壊する */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 10px 0 !important; /* 上下の隙間 */
            width: 100% !important;
        }

        /* 子要素（カラム）を強制的に50%幅にする */
        div[data-testid="stHorizontalBlock"] > div {
            width: 50% !important;
            flex: 0 0 50% !important;
            min-width: 50% !important;
            max-width: 50% !important;
            padding: 5px !important; /* スマホ時の余白を詰める */
        }

        .product-image-container {
            height: 160px !important; /* モバイルで見栄えの良い高さ */
        }
        
        .main-title {
            font-size: 1.5rem !important;
            border-left-width: 6px;
        }
    }

    /* 印刷用 */
    @media print {
        .no-print, [data-testid="stSidebar"] { display: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 🔍 ロジック補助関数 ---

def is_valid_adidas_img(url):
    keywords = ["adidas", "yimg", "bing", "gstatic", "shop-adidas", "mm-adidas"]
    return any(k in url.lower() for k in keywords)

def get_best_image(code, name=""):
    code_str = str(code).strip().upper()
    # 楽天APIなどは変更なし
    return None # (中略: 既存の検索ロジックを維持)

# 🌟 修正：BS列の検出精度を向上
def guess_column_index(columns, target_keywords, exclude_keywords=None):
    if exclude_keywords is None:
        exclude_keywords = ['size', 'サイズ', 'cm', '規格', '寸']
    
    for idx, col in enumerate(columns):
        c_low = str(col).lower()
        # ターゲットにヒットし、かつ除外ワードを含まないものを優先
        if any(tk in c_low for tk in target_keywords):
            if not any(ek in c_low for ek in exclude_keywords):
                return idx
    return 0

def save_auto_save_data(items):
    try:
        with open(AUTO_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except: pass 

# ==========================================
# メイン UI 
# ==========================================
st.markdown('<div class="main-title">📦 商品画像見える君</div>', unsafe_allow_html=True)

# セッション状態の初期化
if "generated" not in st.session_state:
    st.session_state.catalog_items = []
    st.session_state.generated = False

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定・管理")
    concurrency = st.slider("⚡ 検索スピード", 1, 10, 5)
    is_print_mode = st.toggle("コンパクトモード", value=False)
    
    if st.session_state.generated:
        st.subheader("🎯 絞り込み")
        is_new_only = st.checkbox("✨ 新規入荷のみ", key="new_only_toggle")

        items = st.session_state.catalog_items
        # 🌟 修正：BS（カテゴリー）のユニークリスト作成時に空文字を除外
        unique_bs = sorted(list(set([str(i.get("bs", "")).strip() for i in items if str(i.get("bs", "")).strip()])))
        
        sel_bs = []
        if unique_bs:
            col_a, col_b = st.columns(2)
            if col_a.button("全選択"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = True
            if col_b.button("全解除"):
                for b in unique_bs: st.session_state[f"chk_{b}"] = False
            
            with st.container(height=300):
                for b in unique_bs:
                    if st.checkbox(b, key=f"chk_{b}", value=True):
                        sel_bs.append(b)

# --- メインコンテンツ ---
if not st.session_state.generated:
    uploaded_file = st.file_uploader("Excel/CSVをアップロード", type=['xlsx', 'xlsm', 'csv'])
    if uploaded_file:
        # (中略: データ読み込みロジック)
        # 🌟 列割り当て時の自動選択をより厳密に
        # code_col = ...
        # size_col = guess_column_index(columns, ['size', 'サイズ'])
        # bs_col = guess_column_index(columns, ['bs', 'category', '部門'], exclude_keywords=['size', 'サイズ'])
        pass

# カタログ表示部分（ここも修正）
if st.session_state.generated:
    # フィルタリング
    filtered = st.session_state.catalog_items
    if sel_bs:
        filtered = [i for i in filtered if i.get("bs") in sel_bs]
    
    # 📱 カタログのレンダリング
    num_cols = 5 if is_print_mode else 2 # モバイルを意識して標準を2にするか、動的に切り替え
    
    # PC/スマホで出し分けるためのグリッド
    for i in range(0, len(filtered), num_cols):
        cols = st.columns(num_cols)
        for j, item in enumerate(filtered[i:i+num_cols]):
            with cols[j]:
                # 視認性重視のカード表示
                st.markdown(f'''
                    <div class="product-card">
                        <div class="product-title">{item["name"]}</div>
                        <div class="product-details">
                            Art: {item["code"]}<br>
                            Size: {item["size"]}<br>
                            Qty: {item.get("qty","0")}点 / {item.get("status","")}
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
                
                img_url = item.get("manual_url") or item.get("auto_url")
                if img_url:
                    st.markdown(f'<div class="product-image-container"><img src="{img_url}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="product-image-container" style="background:#333;"><div style="color:#666;">No Image</div></div>', unsafe_allow_html=True)
