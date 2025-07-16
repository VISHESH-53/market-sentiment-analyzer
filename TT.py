# --- SETUP ---
# pip install yfinance textblob sqlalchemy pandas matplotlib streamlit beautifulsoup4 requests altair newsapi-python plotly schedule

import yfinance as yf
import pandas as pd
from textblob import TextBlob
import sqlalchemy
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import streamlit as st
import altair as alt
from newsapi import NewsApiClient
import plotly.express as px
import schedule
import time

# --- CONFIG ---
st.set_page_config(page_title="Market Sentiment Analyzer", layout="wide")

# --- Sidebar Controls ---
STOCKS = st.sidebar.multiselect("Select stocks:", ['AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN'], default=['AAPL', 'MSFT', 'TSLA'])
START_DATE = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
END_DATE = st.sidebar.date_input("End Date", datetime.now())

# --- Database URI ---
DB_URI = 'sqlite:///stock_analysis.db'
engine = sqlalchemy.create_engine(DB_URI)

# --- Market Indices ---
MARKET_INDICES = {
    "VIX": "^VIX",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC"
}

# --- News API ---
newsapi = NewsApiClient(api_key='85ee2bd2e1154ca9b865f97ebf666a77') 

# --- 1. Fetch Stock Data ---
def fetch_stock_data(ticker):
    data = yf.download(ticker, start=START_DATE, end=END_DATE, auto_adjust=False)
    data.reset_index(inplace=True)
    data.columns = [col if isinstance(col, str) else col[0] for col in data.columns]
    data['Ticker'] = ticker
    return data

# --- 2. Store in SQLite DB ---
def store_to_db(df, table_name):
    df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')

# --- 3. Fetch News + Sentiment ---
def fetch_real_news(ticker):
    try:
        articles = newsapi.get_everything(
            q=f"{ticker} stock",
            language='en',
            sort_by='relevancy',
            page_size=5
        )
        headlines = [article['title'] for article in articles['articles']]
        sentiments = [TextBlob(h).sentiment.polarity for h in headlines]
        return pd.DataFrame({'Ticker': ticker, 'Headline': headlines, 'Sentiment': sentiments})
    except Exception as e:
        print(f"❌ Failed to fetch news for {ticker}: {e}")
        return pd.DataFrame(columns=['Ticker', 'Headline', 'Sentiment'])

# --- 4. Fetch Market Index Data ---
def fetch_index_data(symbol_dict, start_date, end_date):
    index_df = pd.DataFrame()
    for name, symbol in symbol_dict.items():
        df = yf.download(symbol, start=start_date, end=end_date)[['Close']]
        df.rename(columns={"Close": name}, inplace=True)
        index_df = pd.concat([index_df, df], axis=1)
    index_df.dropna(inplace=True)
    return index_df

# --- 5. Fetch Real Sentiment Series from DB ---
def fetch_sentiment_series_from_db(start_date, end_date):
    query = f"""
        SELECT date(Date) as Date, AVG(Sentiment) as Sentiment
        FROM stock_news
        WHERE date(Date) BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY date(Date)
        ORDER BY Date
    """
    sentiment_df = pd.read_sql(query, engine)
    sentiment_df['Date'] = pd.to_datetime(sentiment_df['Date'])
    sentiment_df.set_index("Date", inplace=True)
    return sentiment_df

# --- MAIN FLOW ---
st.title("📈 Quantitative Market Sentiment Analyzer")

all_data, all_sentiment = [], []

for stock in STOCKS:
    df = fetch_stock_data(stock)
    all_data.append(df)
    store_to_db(df, 'stock_prices')

    sent_df = fetch_real_news(stock)
    all_sentiment.append(sent_df)
    store_to_db(sent_df, 'stock_news')

# --- Load Data from SQLite ---
stock_prices = pd.read_sql("SELECT * FROM stock_prices", engine)
stock_news = pd.read_sql("SELECT * FROM stock_news", engine)

# --- STOCK PRICE CHARTS ---
st.subheader("📉 Stock Prices Over Time")
for stock in STOCKS:
    subset = stock_prices[stock_prices['Ticker'] == stock]
    if not subset.empty:
        subset['Date'] = pd.to_datetime(subset['Date'])
        fig = px.line(subset, x='Date', y='Close', title=f"{stock} Closing Price")
        st.plotly_chart(fig)
    else:
        st.warning(f"No price data available for {stock}.")

# --- SENTIMENT ANALYSIS ---
st.subheader("🧠 Sentiment Analysis of Latest News")
for stock in STOCKS:
    st.markdown(f"**{stock}**")
    news = stock_news[stock_news['Ticker'] == stock][['Headline', 'Sentiment']]
    st.dataframe(news)
    if not news.empty:
        bar_data = news.dropna().set_index('Headline')
        if not bar_data.empty:
            fig = px.bar(bar_data.reset_index(), x='Headline', y='Sentiment', title=f"{stock} News Sentiment")
            st.plotly_chart(fig)
        else:
            st.info("No valid sentiment data to display bar chart.")
    else:
        st.warning("No news data found.")

# --- AVERAGE SENTIMENT BAR CHART ---
st.subheader("📊 Average Sentiment per Stock")
avg_sentiment = stock_news.groupby("Ticker")["Sentiment"].mean().reset_index()
if not avg_sentiment.empty:
    fig = px.bar(avg_sentiment, x='Ticker', y='Sentiment', color='Ticker', title="Average Sentiment")
    st.plotly_chart(fig)
else:
    st.info("No sentiment data available for average sentiment chart.")

# --- SENTIMENT PIE CHARTS ---
st.subheader("🥧 Sentiment Category Distribution")
for stock in STOCKS:
    st.markdown(f"**{stock}**")
    news = stock_news[stock_news['Ticker'] == stock]

    def categorize(p):
        if p > 0.1:
            return "Positive"
        elif p < -0.1:
            return "Negative"
        else:
            return "Neutral"

    if not news.empty:
        news = news.dropna(subset=['Sentiment'])
        news["Category"] = news["Sentiment"].apply(categorize)
        pie_data = news["Category"].value_counts().reset_index()
        pie_data.columns = ["Sentiment", "Count"]

        if not pie_data.empty:
            fig = px.pie(pie_data, names='Sentiment', values='Count', title=f"{stock} Sentiment Distribution")
            st.plotly_chart(fig)
        else:
            st.info("No sentiment distribution available.")
    else:
        st.warning("No news data found for pie chart.")

# --- MARKET RISK ANALYSIS SECTION ---
st.subheader("📉 Market Indices vs Sentiment Score")

# Fetch market index data and sentiment from DB
index_df = fetch_index_data(MARKET_INDICES, START_DATE, END_DATE)
sentiment_series = fetch_sentiment_series_from_db(START_DATE, END_DATE)

# Combine and normalize
if not sentiment_series.empty and not index_df.empty:
    combined_df = pd.merge(index_df, sentiment_series, left_index=True, right_index=True, how='inner')
    normalized_df = combined_df.copy()
    for col in combined_df.columns:
        normalized_df[col] = (combined_df[col] - combined_df[col].min()) / (combined_df[col].max() - combined_df[col].min())

    # Plot
    fig = px.line(normalized_df.reset_index(), x='Date', y=normalized_df.columns,
                  title="Normalized Market Indices vs Sentiment Score")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Not enough sentiment or index data to show comparative analysis.")

# --- OPTIONAL: Background Job for Daily Refresh ---
def job():
    for stock in STOCKS:
        df = fetch_stock_data(stock)
        store_to_db(df, 'stock_prices')
        sent_df = fetch_real_news(stock)
        store_to_db(sent_df, 'stock_news')

schedule.every().day.at("09:00").do(job)

@st.cache_data
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

# Uncomment below line for local background jobs
# run_scheduler()
