from yahoo_fin import stock_info
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests
from curl_cffi import requests

# 텔레그램 토큰/ID
BOT_TOKEN = '7596283010:AAFDWckYKE96cQabSc8f3d8MHbhB8gWuaIU'
CHAT_ID = '6575518263'

# 이동평균선 설정
short_window = 5
medium_window = 20
long_window = 40


# 나스닥 종목 리스트 가져오기
def get_nasdaq_tickers():
    return stock_info.tickers_nasdaq()


# S&P SmallCap 600 종목 리스트 가져오기
def get_SPSC600_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
    tables = pd.read_html(url)

    df = tables[0]
    tickers = df['Symbol'].tolist()

    return tickers


# 러셀2000 종목 리스트 가져오기
def get_RS2000_tickers():
    file_path = 'russell_2000_components.csv'

    df = pd.read_csv(file_path)
    tickers = df['Ticker'].tolist()

    return tickers


# 스테이지 판별 함수
def get_stage(ma5, ma20, ma40):
    if pd.isna(ma5) or pd.isna(ma20) or pd.isna(ma40):
        return None  # NaN 값 있으면 스테이지 계산 불가

    if ma5 > ma20 > ma40:
        return 1
    elif ma20 > ma5 > ma40:
        return 2
    elif ma20 > ma40 > ma5:
        return 3
    elif ma40 > ma20 > ma5:
        return 4
    elif ma40 > ma5 > ma20:
        return 5
    elif ma5 > ma40 > ma20:
        return 6
    else:
        return None


# 3일 연속 간격 증가 확인 함수
def is_gap_increasing(ticker, ma_short, ma_medium, ma_long):
    gap1 = [ma_short.iloc[i][ticker] - ma_medium.iloc[i][ticker] for i in range(3)]
    gap2 = [ma_medium.iloc[i][ticker] - ma_long.iloc[i][ticker] for i in range(3)]
    is_gap1_increasing = gap1[0] > gap1[1] > gap1[2]
    is_gap2_increasing = gap2[0] > gap2[1] > gap2[2]

    return is_gap1_increasing and is_gap2_increasing


# 중복된 스테이지 요약 함수
def compress_stages(lst):
    if not lst:
        return []

    compressed = [lst[0]]  # 첫 번째 값은 무조건 넣고 시작
    for i in range(1, len(lst)):
        if lst[i] != lst[i - 1]:
            compressed.append(lst[i])
    return compressed


# 제1스테이지 유지 일수 확인 함수
def count_consecutive_repeats(lst):
    if not lst:
        return 0

    count = 1  # 첫 번째 항목은 무조건 1번 등장한 것으로 시작
    first_value = lst[0]

    for i in range(1, len(lst)):
        if lst[i] == first_value:
            count += 1
        else:
            break  # 첫 번째 값과 다른 숫자가 나오면 중단

    return count


# 상장폐지 가능 종목 제외 함수
def filter_recommendations(recommendations, non_compliant_tickers):
    return [ticker for ticker in recommendations if ticker not in non_compliant_tickers]


# [주요 알고리즘]
# 스테이지 변환 체크 함수
def check_condition(ticker):
    try:
        data = yf.download(ticker, interval='1d', period='130d', progress=False, session=session)
        if data.empty or len(data) < 130:
            return False

        # SMA
        # ma5 = data['Close'].rolling(window=short_window).mean()
        # ma20 = data['Close'].rolling(window=medium_window).mean()
        # ma40 = data['Close'].rolling(window=long_window).mean()

        # EMA
        ma5 = data['Close'].ewm(span=short_window, adjust=False).mean()
        ma20 = data['Close'].ewm(span=medium_window, adjust=False).mean()
        ma40 = data['Close'].ewm(span=long_window, adjust=False).mean()

        df_ma5 = pd.DataFrame(ma5.iloc[long_window - 1:].iloc[::-1])
        df_ma20 = pd.DataFrame(ma20.iloc[long_window - 1:].iloc[::-1])
        df_ma40 = pd.DataFrame(ma40.iloc[long_window - 1:].iloc[::-1])

        ##### 단,중,장기 이동평균선 3일 연속 향상(미충족시 skip)
        if not (df_ma5.iloc[0][ticker] > df_ma5.iloc[1][ticker] > df_ma5.iloc[2][ticker] and \
                df_ma20.iloc[0][ticker] > df_ma20.iloc[1][ticker] > df_ma20.iloc[2][ticker] and \
                df_ma40.iloc[0][ticker] > df_ma40.iloc[1][ticker] > df_ma40.iloc[2][ticker]):
            return False

        stages = []
        for i in range(0, len(df_ma5)):
            s = get_stage(df_ma5.iloc[i][ticker], df_ma20.iloc[i][ticker], df_ma40.iloc[i][ticker])
            stages.append(s)
        cp_stages = compress_stages(stages)

        ##### 제1스테이지 유지 기간 3일 이상인지 확인
        if count_consecutive_repeats(stages) < 3:
            return False

        ##### 제6스테이지 → 제1스테이지 확인
        if len(cp_stages) < 2:
            return False
        if cp_stages[0] == 1 and cp_stages[1] == 6:
            ##### 단-중-장기 이동평균선 간격 3일 연속 증가(미충족시 skip)
            if not is_gap_increasing(ticker, df_ma5, df_ma20, df_ma40):
                return False
            else:
                return True
        else:
            return False

    except Exception as e:
        print(f"Error with {ticker}: {e}")
        return False


# 조건 만족 종목 찾기
def find_matching_stocks():
    tickers = get_nasdaq_tickers()
    # tickers = get_SPSC600_tickers()
    # tickers = get_RS2000_tickers()
    matched = []
    for ticker in tickers:
        if check_condition(ticker):
            matched.append(ticker)
            print(ticker)
    return matched


# 실행
session = requests.Session(impersonate="chrome")
stocks = find_matching_stocks()

# 상장폐지 가능 종목(Non-compliant Companies) 제외
ncc_df = pd.read_csv(r"C:\\Users\\JiHoon\\OneDrive\\NasdaqNonComplianceIssuers_250506.csv")
<<<<<<< HEAD
=======
# ncc_df = pd.read_csv(r"C:\\Users\\이지훈\\OneDrive\\NasdaqNonComplianceIssuers_250506.csv")
>>>>>>> 580b589334dba4b49dcecc6d42f2a0d7d0c55b15
ncc_tickers = ncc_df["Symbol"].tolist()
len_ncc = len(ncc_tickers)

filtered_stocks = [ticker for ticker in stocks if ticker not in ncc_tickers]
len_stocks = len(filtered_stocks)

print("매수 추천 종목들: ")
print(filtered_stocks)
print("* 매수 추천 종목 개수 :", len_stocks)
print("* 상장폐지 가능 종목 개수 :", len_ncc)

# txt파일 저장
path = "C:\\Users\\JiHoon\\OneDrive\\MA_result.txt"
line = today + '\t' + '\t'.join(stocks) + '\n'

with open(path, 'a', encoding='utf-8') as f:
    f.write(line)

# 텔레그램 전송
message = "[MA 기준 매수 종목 추천" + f"({len_stocks})]" + "\n" + f"({today})" + "\n" + f"{filtered_stocks}"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
response = requests.post(url, data={'chat_id': CHAT_ID, 'text': message})

if response.status_code == 200:
    print("✅ 텔레그램 전송 성공!")
else:
    print(f"❌ 오류 발생: {response.text}")