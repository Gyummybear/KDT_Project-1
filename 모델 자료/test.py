import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

#데이터 정의 (BEV+PHEV 합산 및 LME 가격)
years = list(range(2016, 2026))
# ev_sales_mil : EV_Data_Explorer_2026.xlsx > 시트 GEVO_EV_2026
#                region_country='World' / parameter='EV sales' / mode='Cars'
#                powertrain∈{BEV, PHEV} → 연도별 합산 후 백만 대 단위 변환

ev_sales_mil = [0.78, 1.2, 2.0, 2.2, 3.1, 6.5, 10.2, 13.7, 17.0, 21.0] # 백만대 단위
# al_price     : 2016_2025_광물자원가격_알루미늄_년간.xlsx > 시트 RsrcPrice
#                기준일(연도) / 기준가격(USD/ton)
al_price = [1604.89, 1968.74, 2110.08, 1791.13, 1704.02, 2479.62, 2703.18, 2249.54, 2418.88, 2632.07]

df = pd.DataFrame({'Year': years, 'EV_Sales_Mil': ev_sales_mil, 'Al_Price': al_price})

# 그래프 생성
fig, ax1 = plt.subplots(figsize=(10, 5.5))
sns.set_theme(style='white')

# 왼쪽 축: EV 판매량 (막대)
color_ev = '#4C72B0'
ax1.set_xlabel('Year', fontsize=11, fontweight='bold', labelpad=10)
ax1.set_ylabel('Global EV Sales (BEV+PHEV, Millions)', color=color_ev, fontsize=11, fontweight='bold')
ax1.bar(df['Year'], df['EV_Sales_Mil'], color=color_ev, alpha=0.5, width=0.4, label='EV Sales')
ax1.tick_params(axis='y', labelcolor=color_ev)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

# 오른쪽 축: 알루미늄 가격 (선)
ax2 = ax1.twinx()
color_al = '#C44E52'
ax2.set_ylabel('LME Aluminum Price (USD/ton)', color=color_al, fontsize=11, fontweight='bold')
ax2.plot(df['Year'], df['Al_Price'], color=color_al, marker='o', linewidth=2.5, markersize=8, label='Aluminum Price')
ax2.tick_params(axis='y', labelcolor=color_al)

plt.title('Step 1: Trend Coupling Baseline (2016-2025)', fontsize=14, fontweight='bold', pad=15)
fig.tight_layout()
plt.savefig('01_EV판매량_알루미늄가격_추세.png', dpi=300)
plt.close()
df.to_csv('01_EV판매량_알루미늄가격_데이터.csv', index=False)
print("[단계 1] EV 판매량과 알루미늄 가격 추세 시각화가 완료되었습니다.")
print(f"연도 범위      : {years[0]}-{years[-1]}")
print(f"데이터 개수     : {len(df)}")
print(f"출력 파일       : 01_EV판매량_알루미늄가격_추세.png, 01_EV판매량_알루미늄가격_데이터.csv\n")



import scipy.stats as stats

# 시차(Time-Lag) 매칭 데이터 프레임 구축 (가격 기준 2016~2023)
# t년도 가격에 t+1년도 판매량 매칭
df_train = pd.DataFrame({
    'Price_Year': [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023],
    'EV_Year_Next': [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024],
    'EV_Sales_Next_Mil': [1.2, 2.0, 2.2, 3.1, 6.5, 10.2, 13.7, 17.0], # t+1년 판매량
    'Al_Price_Current': [1604.89, 1968.74, 2110.08, 1791.13, 1704.02, 2479.62, 2703.18, 2249.54] # t년 가격
})

corr_coef, p_value = stats.pearsonr(df_train['EV_Sales_Next_Mil'], df_train['Al_Price_Current'])

plt.figure(figsize=(9, 6))
sns.set_theme(style='whitegrid')

# 95% 신뢰구간을 포함한 산점도 및 선형 경향선
sns.regplot(
    data=df_train, x='EV_Sales_Next_Mil', y='Al_Price_Current', color='#2b5c8f',
    scatter_kws={'s': 130, 'alpha': 0.8, 'edgecolor': 'w', 'linewidths': 1.5},
    line_kws={'color': '#d62728', 'linewidth': 2}
)

# 데이터 포인트마다 매칭 정보 라벨링 (예: P:'16은 2016년 가격, EV:'17은 2017년 판매량)
for i, row in df_train.iterrows():
    plt.annotate(f"P:'{str(int(row['Price_Year']))[2:]} (EV:'{str(int(row['EV_Year_Next']))[2:]})", 
                 (row['EV_Sales_Next_Mil'] + 0.3, row['Al_Price_Current'] - 30), fontsize=9, fontweight='bold')

# 통계치 요약 박스 표시
text_box = f"Pearson R = {corr_coef:.4f}\np-value = {p_value:.4f}\n(Strong Time-Lagged Corr)"
plt.gca().text(0.05, 0.92, text_box, transform=plt.gca().transAxes, fontsize=10,
            verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='gray'))

plt.title('Step 2: Time-Lagged Correlation with 95% Confidence Interval', fontsize=13, fontweight='bold', pad=15)
plt.xlabel('Global EV Sales in Next Year (t+1, Millions)', fontsize=11)
plt.ylabel('LME Aluminum Price in Current Year (t, USD/ton)', fontsize=11)
plt.xlim(0, 20)
plt.ylim(1400, 3000)
plt.tight_layout()
plt.savefig('02_시차기반_상관분석.png', dpi=300)
plt.close()

regression_result = stats.linregress(df_train['EV_Sales_Next_Mil'], df_train['Al_Price_Current'])
slope, intercept = regression_result.slope, regression_result.intercept
r_squared = regression_result.rvalue ** 2
if abs(corr_coef) >= 0.7 and p_value < 0.05:
    corr_judgement = "강한 상관관계로 회귀 분석 진행이 타당합니다."
elif abs(corr_coef) >= 0.5 and p_value < 0.1:
    corr_judgement = "중간 정도 상관관계로 추가 검증이 필요합니다."
else:
    corr_judgement = "현재 데이터로는 회귀 분석 진행에 주의가 필요합니다."
df_train.to_csv('02_시차기반_상관분석_데이터.csv', index=False)
print("[단계 2] 시차 기반 상관분석이 완료되었습니다.")
print(f"Pearson 상관계수 : {corr_coef:.4f}")
print(f"p-값           : {p_value:.4f}")
print(f"R^2            : {r_squared:.4f}")
print(f"회귀 판정       : {corr_judgement}")
print(f"출력 파일        : 02_시차기반_상관분석.png, 02_시차기반_상관분석_데이터.csv\n")


# 회귀분석 결과 적용 (Slope, Intercept)
# Step 2에서 계산한 회귀모델 파라미터를 그대로 사용
# 검증용 데이터셋 세팅 (2024~2025 가격 기준)
# 2024년 가격($2418.88)에는 2025년 판매량(21.0Mil)이 매칭됨
df_test = pd.DataFrame({
    'Price_Year': [2024, 2025],
    'EV_Sales_Next_Mil': [21.0, np.nan], # 2025년 가격에 매칭될 2026년 판매량 데이터는 원본에 없으므로 2024년 가격 기준 1개년 검증 진행
    'Al_Price_Current': [2418.88, 2632.07]
}).dropna()

# 2024년 가격 예측치 계산
df_test['Predicted_Price'] = slope * df_test['EV_Sales_Next_Mil'] + intercept

plt.figure(figsize=(10, 6))
sns.set_theme(style='whitegrid')

# 1) 학습에 사용된 기존 데이터 분포
plt.scatter(df_train['EV_Sales_Next_Mil'], df_train['Al_Price_Current'], 
            color='#1f77b4', s=130, label='Train Data (Price 2016-2023)', zorder=3)

# 2) 2024년 실제 단가 위치
plt.scatter(df_test['EV_Sales_Next_Mil'], df_test['Al_Price_Current'], 
            color='#2ca02c', marker='X', s=180, label='Actual Price (2024)', zorder=4)

# 3) 2024년 모델이 예측한 단가 위치
plt.scatter(df_test['EV_Sales_Next_Mil'], df_test['Predicted_Price'], 
            color='#d62728', marker='o', s=130, label='Predicted Price (2024)', zorder=4)

# 회귀 연장선 플롯
x_line = np.linspace(0, 24, 100)
y_line = slope * x_line + intercept
plt.plot(x_line, y_line, color='gray', linestyle='--', alpha=0.7, label='Regression Predictive Line')

# 2024년 검증 포인트 라벨링 및 오차 시각화 구상
for i, row in df_test.iterrows():
    plt.annotate(f"P:'24 Actual", (row['EV_Sales_Next_Mil'] + 0.4, row['Al_Price_Current'] - 40), fontsize=10, color='green', fontweight='bold')
    plt.annotate(f"P:'24 Pred", (row['EV_Sales_Next_Mil'] + 0.4, row['Predicted_Price'] + 20), fontsize=10, color='red', fontweight='bold')
    # 오차 폭을 수직 점선으로 표시
    plt.vlines(row['EV_Sales_Next_Mil'], row['Al_Price_Current'], row['Predicted_Price'], colors='purple', linestyles=':', linewidth=2)

plt.title('Step 3: Model Verification & Backtesting (Predicting 2024)', fontsize=13, fontweight='bold', pad=15)
plt.xlabel('Global EV Sales in Next Year (BEV+PHEV, Millions)', fontsize=11)
plt.ylabel('LME Aluminum Price in Current Year (USD/ton)', fontsize=11)
plt.xlim(0, 24)
plt.ylim(1300, 3300)
plt.legend(fontsize=10, loc='upper left')
plt.tight_layout()
plt.savefig('03_모델검증_백테스팅.png', dpi=300)
plt.close()

df_test['Error'] = df_test['Al_Price_Current'] - df_test['Predicted_Price']
df_test['Abs_Error'] = df_test['Error'].abs()
df_test['Abs_Error_Pct'] = df_test['Abs_Error'] / df_test['Al_Price_Current'] * 100
mae = df_test['Abs_Error'].mean()
mse = (df_test['Error'] ** 2).mean()
rmse = np.sqrt(mse)
mean_pct = df_test['Abs_Error_Pct'].mean()
if mae < 100:
    perf_desc = "양호"
elif mae < 200:
    perf_desc = "보통"
else:
    perf_desc = "미흡"
df_test.to_csv('03_모델검증_백테스팅_데이터.csv', index=False)
print("[단계 3] 모델 검증이 완료되었습니다.")
print(f"기울기       : {slope:.4f}")
print(f"절편         : {intercept:.2f}")
print(f"테스트 MAE    : {mae:.2f}")
print(f"테스트 RMSE   : {rmse:.2f}")
print(f"평균 오차율    : {mean_pct:.2f}%")
print(f"모델 신뢰도    : {perf_desc}")
for _, row in df_test.iterrows():
    print(f"2024년 실제={row['Al_Price_Current']:.2f}, 예측={row['Predicted_Price']:.2f}, 오차={row['Error']:.2f}, 오차율={row['Abs_Error_Pct']:.2f}%")
print(f"출력 파일     : 03_모델검증_백테스팅.png, 03_모델검증_백테스팅_데이터.csv\n")

print("[시각화 완료] 01_EV판매량_알루미늄가격_추세.png, 01_EV판매량_알루미늄가격_데이터.csv, 02_시차기반_상관분석.png, 02_시차기반_상관분석_데이터.csv, 03_모델검증_백테스팅.png, 03_모델검증_백테스팅_데이터.csv 파일이 성공적으로 생성되었습니다.")