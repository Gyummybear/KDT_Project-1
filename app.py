<<<<<<< HEAD
# app.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np

# 분리한 모듈 임포트
from scrapper import fetch_komis_mineral_prices
from file import save_data_to_csv, get_latest_data

st.set_page_config(page_title="Mineral Insight", layout="wide")

# 스파크라인(미니 차트) 생성 함수
def create_sparkline(change_rate):
    color = 'red' if change_rate > 0 else 'blue'
    y_data = np.random.randn(20).cumsum() if change_rate > 0 else -np.random.randn(20).cumsum()
    
    fig = go.Figure(data=go.Scatter(y=y_data, mode='lines', line=dict(color=color, width=2)))
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
        height=50, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

# --- 사이드바: 데이터 업데이트 컨트롤 ---
with st.sidebar:
    st.header("⚙️ 시스템 관리")
    if st.button("🔄 최신 광물 데이터 수집"):
        with st.spinner("데이터를 수집 중입니다..."):
            new_data = fetch_komis_mineral_prices()
            if save_data_to_csv(new_data):
                st.success("데이터 업데이트 성공!")
            else:
                st.error("데이터 업데이트 실패")

# --- 메인 화면: 대시보드 ---
st.title("오늘의 광물 인사이트")
st.markdown("주요 광물 가격 동향과 공급망 리스크를 한눈에 확인하세요.")

# 최신 데이터 불러오기
df = get_latest_data()

if df.empty:
    st.info("좌측 사이드바에서 '최신 광물 데이터 수집' 버튼을 눌러 데이터를 초기화해주세요.")
else:
    st.subheader("주요 광물 가격 동향")
    
    # 5개의 컬럼으로 UI 구성
    cols = st.columns(len(df))
    status_colors = {"위험": "#ff4b4b", "주의": "#ffa421", "안정": "#00c04b"}
    
    # df.iterrows() 앞에 enumerate를 붙여서 i에 0, 1, 2... 순서가 들어가게 합니다.
    for i, (idx, row) in enumerate(df.iterrows()):
        with cols[i]:
            st.write(f"**{row['광물']}**")
            
            # 가격 포맷팅 및 Metric 표시
            price_str = f"{row['단위'].split('/')[0]} {row['가격']:,} /t"
            st.metric(label="", value=price_str, delta=f"{row['등락률']}%", label_visibility="collapsed")
            
            # 차트
            st.plotly_chart(create_sparkline(row['등락률']), use_container_width=True, config={'displayModeBar': False})
            
            # 상태 뱃지
            bg_color = status_colors.get(row['상태'], "gray")
            st.markdown(f"<span style='background-color:{bg_color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;'>{row['상태']}</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("데이터 테이블 (Raw Data)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    with col2:
        st.subheader("주요 뉴스 요약 (AI 요약)")
        st.info("1. 인도네시아 니켈 수출 쿼터 축소 검토\n\n공급 감소 우려로 가격 상승세 (Reuters)")
=======
# app.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np

# 분리한 모듈 임포트
from scrapper import fetch_komis_mineral_prices
from file import save_data_to_csv, get_latest_data

st.set_page_config(page_title="Mineral Insight", layout="wide")

# 스파크라인(미니 차트) 생성 함수
def create_sparkline(change_rate):
    color = 'red' if change_rate > 0 else 'blue'
    y_data = np.random.randn(20).cumsum() if change_rate > 0 else -np.random.randn(20).cumsum()
    
    fig = go.Figure(data=go.Scatter(y=y_data, mode='lines', line=dict(color=color, width=2)))
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
        height=50, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

# --- 사이드바: 데이터 업데이트 컨트롤 ---
with st.sidebar:
    st.header("⚙️ 시스템 관리")
    if st.button("🔄 최신 광물 데이터 수집"):
        with st.spinner("데이터를 수집 중입니다..."):
            new_data = fetch_komis_mineral_prices()
            if save_data_to_csv(new_data):
                st.success("데이터 업데이트 성공!")
            else:
                st.error("데이터 업데이트 실패")

# --- 메인 화면: 대시보드 ---
st.title("오늘의 광물 인사이트")
st.markdown("주요 광물 가격 동향과 공급망 리스크를 한눈에 확인하세요.")

# 최신 데이터 불러오기
df = get_latest_data()

if df.empty:
    st.info("좌측 사이드바에서 '최신 광물 데이터 수집' 버튼을 눌러 데이터를 초기화해주세요.")
else:
    st.subheader("주요 광물 가격 동향")
    
    # 5개의 컬럼으로 UI 구성
    cols = st.columns(len(df))
    status_colors = {"위험": "#ff4b4b", "주의": "#ffa421", "안정": "#00c04b"}
    
    # df.iterrows() 앞에 enumerate를 붙여서 i에 0, 1, 2... 순서가 들어가게 합니다.
    for i, (idx, row) in enumerate(df.iterrows()):
        with cols[i]:
            st.write(f"**{row['광물']}**")
            
            # 가격 포맷팅 및 Metric 표시
            price_str = f"{row['단위'].split('/')[0]} {row['가격']:,} /t"
            st.metric(label="", value=price_str, delta=f"{row['등락률']}%", label_visibility="collapsed")
            
            # 차트
            st.plotly_chart(create_sparkline(row['등락률']), use_container_width=True, config={'displayModeBar': False})
            
            # 상태 뱃지
            bg_color = status_colors.get(row['상태'], "gray")
            st.markdown(f"<span style='background-color:{bg_color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;'>{row['상태']}</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("데이터 테이블 (Raw Data)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    with col2:
        st.subheader("주요 뉴스 요약 (AI 요약)")
        st.info("1. 인도네시아 니켈 수출 쿼터 축소 검토\n\n공급 감소 우려로 가격 상승세 (Reuters)")
>>>>>>> 5306a7a77cb0664bdbdb8971070fa4fac74ef945
        st.info("2. 칠레 리튬 생산 감소 전망\n\n주요 리튬 기업들의 생산 차질 (Bloomberg)")