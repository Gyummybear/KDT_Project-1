import streamlit as st
import plotly.graph_objects as go
import numpy as np
import google.generativeai as genai  
import pandas as pd 
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# 분리한 모듈 임포트 
from scrapper import fetch_komis_mineral_prices
from file import save_data_to_csv, get_latest_data
from plotly.subplots import make_subplots

st.set_page_config(page_title="Mineral Insight", layout="wide")

# ==========================================
# [신규] 동적 지원 모델 탐색 함수
# 사용자의 환경 및 API가 허용하는 유효한 모델 명칭을 실시간으로 검색합니다.
# ==========================================
def get_supported_model():
    try:
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        # 권장하는 최신 모델 순서대로 탐색 및 매칭
        preferences = [
            'models/gemini-1.5-flash',
            'gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'gemini-1.5-pro'
        ]
        for pref in preferences:
            if pref in available_models:
                return pref
        
        # 선호 모델이 없을 경우 지원 대상 중 가장 첫 번째 모델 반환
        if available_models:
            return available_models[0]
            
    except Exception:
        pass
    
    # 예외적인 상황 발생 시 최종 기본값 반환
    return 'gemini-1.5-flash'


# ==========================================
# 스파크라인(미니 차트) 생성 함수
# ==========================================
def create_sparkline(change_rate, end_date_str):
    color = 'red' if change_rate > 0 else 'blue'
    y_data = np.random.randn(20).cumsum() if change_rate > 0 else -np.random.randn(20).cumsum()
    
    end_date = pd.to_datetime(end_date_str)
    x_data = pd.date_range(end=end_date, periods=20)
    
    fig = go.Figure(data=go.Scatter(
        x=x_data, 
        y=y_data, 
        mode='lines', 
        line=dict(color=color, width=2),
        hovertemplate='일시: %{x|%Y-%m-%d %H:%M}<br>지표: %{y:.2f}<extra></extra>' 
    ))
    
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
        height=50, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

# ==========================================
# 실시간 전기차 경제 뉴스 수집 및 AI 분석 함수 (개선 버전)
# ==========================================
def get_ev_news_summary(api_key):
    try:
        # 1. 뉴스 데이터 수집
        query = urllib.parse.quote("전기차 시장 OR 전기차 경제")
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=7)
        root = ET.parse(res).getroot()

        news_texts = ""
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            title_clean = title.replace('<b>', '').replace('</b>', '')
            desc_clean = desc.replace('<b>', '').replace('</b>', '')[:100]
            news_texts += f"- 제목: {title_clean}\n  내용: {desc_clean}\n\n"

        if not news_texts:
            return "현재 수집된 관련 뉴스가 없습니다."

        # 2. AI 분석 진행
        genai.configure(api_key=api_key)
        
        # 동적 모델 할당 적용
        model_name = get_supported_model()
        
        prompt = f"""
        당신은 글로벌 자동차 산업 및 전장 부품 시장을 분석하는 최고 수준의 기술 영업 전략가입니다.
        아래는 방금 수집된 '전기차 시장 및 경제' 관련 최신 실시간 뉴스들입니다.
        
        [최신 뉴스 데이터]
        {news_texts}
        
        이 뉴스들을 종합적으로 분석하여, 전장 부품(와이어 하네스 등)을 납품하는 B2B 기업의 기술 영업 사원이 
        고객사 미팅 가기 전 반드시 알아야 할 '핵심 경제 동향과 세일즈 인사이트'를 요약해 주세요.
        
        [출력 조건]
        - 뉴스에 나온 팩트를 기반으로 기술 영업에 도움되는 거시적 통찰을 제공할 것.
        - 1. 시장 흐름 요약 / 2. 리스크 및 기회 요인 / 3. 영업 전략 포인트 형식으로 3단락으로 나누어 작성할 것.
        - 비즈니스 전문가의 정중하고 명확한 어조(하십시오체)를 사용할 것.
        """
        
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"뉴스 수집 또는 AI 분석 중 오류가 발생했습니다: {e}"


# ==========================================
# --- 사이드바: 데이터 업데이트 및 AI 설정 관리 ---
# ==========================================
with st.sidebar:
    st.header("⚙️ 시스템 관리")
    if st.button("🔄 최신 광물 데이터 수집"):
        with st.spinner("데이터를 수집 중입니다..."):
            new_data = fetch_komis_mineral_prices()
            if save_data_to_csv(new_data):
                st.success("데이터 업데이트 성공!")
            else:
                st.error("데이터 업데이트 실패")
                
    st.markdown("---")
    st.header("🔑 AI 인증 설정")
    
    if "GEMINI_API_KEY" in st.secrets:
        gemini_api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ Gemini AI 자동 연결됨")
    else:
        gemini_api_key = st.text_input(
            "Gemini API Key", 
            type="password", 
            help="Google AI Studio에서 발급받은 API 키를 입력하세요."
        )

# ==========================================
# --- 메인 화면: 대시보드 ---
# ==========================================
st.title("오늘의 광물 인사이트")
st.markdown("주요 광물 가격 동향과 공급망 리스크를 한눈에 확인하세요.")

df = get_latest_data()

if df.empty:
    st.info("좌측 사이드바에서 '최신 광물 데이터 수집' 버튼을 눌러 데이터를 초기화해주세요.")
else:
    st.subheader("주요 광물 가격 동향")
    
    cols = st.columns(len(df))
    status_colors = {"위험": "#ff4b4b", "주의": "#ffa421", "안정": "#00c04b"}
    
    for i, (idx, row) in enumerate(df.iterrows()):
        with cols[i]:
            st.write(f"**{row['광물']}**")
            price_str = f"{row['단위'].split('/')[0]} {row['가격']:,} /t"
            st.metric(label="", value=price_str, delta=f"{row['등락률']}%", label_visibility="collapsed")
            st.plotly_chart(create_sparkline(row['등락률'], row['수집일시']), use_container_width=True, config={'displayModeBar': False})
            st.caption(f"🕒 {row['수집일시'][5:16]} 기준")
            
            bg_color = status_colors.get(row['상태'], "gray")
            st.markdown(f"<span style='background-color:{bg_color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;'>{row['상태']}</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("데이터 테이블 (Raw Data)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    with col2:
        st.subheader("💡 실시간 AI 공급망 리스크 분석")
        
        if not gemini_api_key:
            st.warning("⚠️ 좌측 사이드바의 'AI 인증 설정'에 Gemini API Key를 입력하시면 분석 브리핑이 생성됩니다.")
        else:
            if st.button("✨ AI 분석 리포트 생성"):
                with st.spinner("Gemini가 현재 물가 지표와 리스크 요인을 분석 중입니다..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        
                        mineral_status_text = ""
                        for _, r in df.iterrows():
                            mineral_status_text += f"- {r['광물']}: 현재가 {r['가격']}원({r['단위']}), 등락률 {r['등락률']}%, 리스크 상태: {r['상태']}\n"
                        
                        prompt = f"""
                        당신은 글로벌 원자재 분석가이자 B2B 기술 영업 분야의 구매 리스크 관리 전문가입니다.
                        아래는 오늘 자 시스템에 수집된 주요 광물 자원의 가격 동향 정보입니다.
                        
                        [현재 광물 시장 데이터]
                        {mineral_status_text}
                        
                        위 데이터와 최근의 글로벌 물가 상승률(인플레이션 변동성), 전방 수요 산업 지표를 종합적으로 고려하여,
                        기술 영업 담당자가 공급망 리스크에 즉각 대응할 수 있도록 핵심 브리핑 2가지를 요약하여 작성해 주세요.
                        
                        [출력 조건]
                        - 각 항목은 비즈니스 분석 어조로 작성하되, 구체적인 리스크 요인(수출 규제, 생산 차질 등)을 명확히 짚어주세요.
                        - 출력 포맷은 정확히 아래 형식을 지켜주세요.
                        1. 요약내용
                        
                        2. 요약내용
                        """
                        
                        # 동적 모델 탐색 적용
                        model_name = get_supported_model()
                        model = genai.GenerativeModel(model_name)
                        final_response = model.generate_content(prompt)
                        
                        if final_response:
                            st.info(final_response.text)
                        else:
                            st.error("AI 분석 결과가 비어 있습니다.")
                            
                    except Exception as e:
                        st.error(f"AI 분석 리포트를 생성하는 과정에서 오류가 발생했습니다: {e}")

# ==========================================
# 5. 상관관계 분석 (전기차 수요 vs 알루미늄 가격)
# ==========================================
st.markdown("---")
st.subheader("📈 산업 지표 상관관계 분석 (EV vs Aluminum)")

try:
    corr_data = pd.DataFrame({
        '연도': [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        '전기차판매량': [2100000, 2200000, 3100000, 6600000, 10500000, 14000000, 17000000, 20500000],
        '알루미늄가격': [2110, 1794, 1704, 2480, 2707, 2250, 2400, 2650]
    })

    fig_corr = make_subplots(specs=[[{"secondary_y": True}]])

    fig_corr.add_trace(
        go.Scatter(x=corr_data['연도'], y=corr_data['알루미늄가격'], 
                   name="알루미늄 가격 (USD/t)", mode='lines+markers', 
                   line=dict(color='#2E86C1', width=3)),
        secondary_y=False,
    )

    fig_corr.add_trace(
        go.Bar(x=corr_data['연도'], y=corr_data['전기차판매량'], 
               name="글로벌 전기차 판매량 (대)", marker_color='rgba(235, 152, 78, 0.6)'),
        secondary_y=True,
    )

    fig_corr.update_layout(
        title_text="전방 산업 수요(EV)와 원자재(Aluminum) 가격 동향",
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
    )
    
    fig_corr.update_yaxes(title_text="<b>알루미늄 가격</b> (USD/t)", secondary_y=False)
    fig_corr.update_yaxes(title_text="<b>전기차 판매량</b> (대)", showgrid=False, secondary_y=True)

    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("💡 **인사이트:** 전기차 판매량이 급증하는 시점(2021년 이후)에 차체 경량화 배터리 케이블의 주재료인 알루미늄 가격의 동반 상승 압력이 관찰됩니다.")

except Exception as e:
    st.error(f"상관관계 시각화 중 오류가 발생했습니다: {e}")

# ==========================================
# 6. 실시간 전기차 경제 뉴스 AI 분석
# ==========================================
st.markdown("---")
st.subheader("📰 실시간 전기차 시장 경제 동향 (AI 요약)")

if not gemini_api_key:
    st.warning("⚠️ 좌측 사이드바에 Gemini API Key를 입력하시면 최신 전기차 경제 뉴스 AI 분석 기능이 활성화됩니다.")
else:
    if st.button("🌐 실시간 EV 경제 뉴스 AI 브리핑 받기"):
        with st.spinner("최신 경제 기사를 수집하여 AI가 분석 중입니다. 잠시만 기다려주세요..."):
            ev_insight = get_ev_news_summary(gemini_api_key)
            if "오류가 발생했습니다" in ev_insight or "지원되는 AI 모델을 호출하지 못했습니다" in ev_insight:
                st.error(ev_insight)
            else:
                st.success("✅ 실시간 뉴스 분석 완료!")
                st.info(ev_insight)