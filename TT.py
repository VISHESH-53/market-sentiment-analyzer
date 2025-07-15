# Quantitative Market Sentiment Analyzer with MySQL & Streamlit Dashboard

# --- SETUP ---
# pip install yfinance textblob sqlalchemy pandas matplotlib streamlit mysql-connector-python beautifulsoup4 requests altair newsapi-python plotly schedule

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
STOCKS = st.sidebar.multiselect("Select stocks:", ['AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN'], default=['AAPL', 'MSFT', 'TSLA'])
START_DATE = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
END_DATE = st.sidebar.date_input("End Date", datetime.now())

# --- MySQL Database URI ---
DB_URI = 'mysql+mysqlconnector://root:vishu@localhost:3306/stock_analysis'
engine = sqlalchemy.create_engine(DB_URI)

# --- Reset tables (DEV ONLY) ---
with engine.connect() as conn:
    conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS stock_prices"))
    conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS stock_news"))

# --- 1. FETCH STOCK DATA ---
def fetch_stock_data(ticker):
    data = yf.download(ticker, start=START_DATE, end=END_DATE, auto_adjust=False)
    data.reset_index(inplace=True)
    data.columns = [col if isinstance(col, str) else col[0] for col in data.columns]
    data['Ticker'] = ticker
    return data

# --- 2. STORE IN DATABASE ---
def store_to_db(df, table_name):
    df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')

# --- 3. REAL NEWS & SENTIMENT ANALYSIS ---
newsapi = NewsApiClient(api_key='85ee2bd2e1154ca9b865f97ebf666a77') 

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

# --- MAIN FLOW ---
all_data = []
all_sentiment = []

for stock in STOCKS:
    df = fetch_stock_data(stock)
    all_data.append(df)
    store_to_db(df, 'stock_prices')

    sent_df = fetch_real_news(stock)
    all_sentiment.append(sent_df)
    store_to_db(sent_df, 'stock_news')

# --- STREAMLIT DASHBOARD ---
st.set_page_config(page_title="Market Sentiment Analyzer", layout="wide")
st.title("📈 Quantitative Market Sentiment Analyzer")

# Load Data from DB
stock_prices = pd.read_sql("SELECT * FROM stock_prices", engine)
stock_news = pd.read_sql("SELECT * FROM stock_news", engine)

# Show price chart
st.subheader("Stock Prices Over Time")
for stock in STOCKS:
    subset = stock_prices[stock_prices['Ticker'] == stock]
    if not subset.empty:
        subset['Date'] = pd.to_datetime(subset['Date'])
        fig = px.line(subset, x='Date', y='Close', title=f"{stock} Closing Price")
        st.plotly_chart(fig)
    else:
        st.warning(f"No price data available for {stock}.")

# Show sentiment analysis
st.subheader("Sentiment Analysis of Latest News")
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

# Avg Sentiment per Stock - Bar Chart
st.subheader("📊 Average Sentiment per Stock")
avg_sentiment = stock_news.groupby("Ticker")["Sentiment"].mean().reset_index()
if not avg_sentiment.empty:
    fig = px.bar(avg_sentiment, x='Ticker', y='Sentiment', color='Ticker', title="Average Sentiment")
    st.plotly_chart(fig)
else:
    st.info("No sentiment data available for average sentiment chart.")

# Pie Chart of Sentiment Categories
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

# Background scheduler to update data daily (active)
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

# Uncomment to run scheduler inside app
# run_scheduler()
