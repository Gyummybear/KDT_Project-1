# file.py
import pandas as pd
import os

DATA_FILE_PATH = "mineral_data.csv"

def save_data_to_csv(df):
    """
    데이터프레임을 CSV 파일로 저장합니다. 
    기존 파일이 있으면 아래에 추가(append)합니다.
    """
    if df is None or df.empty:
        return False
        
    # 파일이 존재하지 않으면 헤더 포함 저장, 존재하면 헤더 제외하고 추가
    if not os.path.exists(DATA_FILE_PATH):
        df.to_csv(DATA_FILE_PATH, index=False, encoding='utf-8-sig')
    else:
        df.to_csv(DATA_FILE_PATH, mode='a', header=False, index=False, encoding='utf-8-sig')
    
    return True

def load_data_from_csv():
    """
    저장된 CSV 파일에서 데이터를 불러옵니다.
    """
    if not os.path.exists(DATA_FILE_PATH):
        return pd.DataFrame() # 파일이 없으면 빈 데이터프레임 반환
        
    df = pd.read_csv(DATA_FILE_PATH, encoding='utf-8-sig')
    return df

def get_latest_data():
    """
    가장 최근에 수집된 데이터만 필터링하여 반환합니다.
    """
    df = load_data_from_csv()
    if df.empty:
        return df
        
    # 수집일시 기준으로 가장 최근 시간의 데이터만 추출
    latest_time = df['수집일시'].max()
    latest_df = df[df['수집일시'] == latest_time].copy()
    
    return latest_df