# Quantitative Market Sentiment Analyzer — Cleaned Version ✅

# --- INSTALL REQUIRED PACKAGES ---
# pip install yfinance textblob newsapi-python pandas streamlit plotly

import yfinance as yf
import pandas as pd
from textblob import TextBlob
from datetime import datetime, timedelta
import streamlit as st
from newsapi import NewsApiClient
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="📊 Market Sentiment Analyzer", layout="wide")
st.title("📈 Quantitative Market Sentiment Analyzer")

# --- USER INPUT ---
STOCKS = st.sidebar.multiselect("Select stocks:", ['AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN'], default=['AAPL'])
START_DATE = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
END_DATE = st.sidebar.date_input("End Date", datetime.now())

# --- NEWS API KEY (Replace with your key) ---
NEWS_API_KEY = "85ee2bd2e1154ca9b865f97ebf666a77"
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

# --- UTILITY FUNCTIONS ---
def fetch_stock_data(ticker):
    df = yf.download(ticker, start=START_DATE, end=END_DATE)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)  # Flatten MultiIndex

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]  # Select only required columns
    df.reset_index(inplace=True)
    df['Ticker'] = ticker
    return df


def fetch_news_sentiment(ticker):
    try:
        articles = newsapi.get_everything(q=f"{ticker} stock", language="en", sort_by="relevancy", page_size=10)
        headlines = [article['title'] for article in articles['articles']]
        sentiments = [TextBlob(headline).sentiment.polarity for headline in headlines]
        return pd.DataFrame({'Date': datetime.now().date(), 'Ticker': ticker, 'Headline': headlines, 'Sentiment': sentiments})
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'Headline', 'Sentiment'])

# --- DATA INGESTION ---
price_frames = []
sentiment_frames = []

for stock in STOCKS:
    stock_df = fetch_stock_data(stock)
    news_df = fetch_news_sentiment(stock)

    price_frames.append(stock_df)
    sentiment_frames.append(news_df)

# --- COMBINE ALL DATA ---
stock_prices = pd.concat(price_frames, ignore_index=True)
stock_news = pd.concat(sentiment_frames, ignore_index=True)

# --- PRICE CHART ---
st.subheader("📉 Stock Closing Prices")
for stock in STOCKS:
    subset = stock_prices[stock_prices['Ticker'] == stock].copy()

    if subset.empty or 'Date' not in subset.columns or 'Close' not in subset.columns:
        st.warning(f"No valid price data available for {stock}")
        continue

    try:
        subset['Date'] = pd.to_datetime(subset['Date'])
        fig = px.line(subset, x='Date', y='Close', title=f"{stock} Closing Price")
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error plotting data for {stock}: {e}")

# --- NEWS SENTIMENT TABLE ---
st.subheader("📰 Latest News Sentiment")
for stock in STOCKS:
    st.markdown(f"### {stock}")
    news_subset = stock_news[stock_news['Ticker'] == stock]
    if not news_subset.empty:
        st.dataframe(news_subset[['Headline', 'Sentiment']])
    else:
        st.info("No news data found.")

# --- AVERAGE SENTIMENT BAR ---
st.subheader("📊 Average Sentiment per Stock")
if not stock_news.empty:
    avg_sentiment = stock_news.groupby("Ticker")["Sentiment"].mean().reset_index()
    fig = px.bar(avg_sentiment, x="Ticker", y="Sentiment", color="Ticker", title="Average Sentiment")
    st.plotly_chart(fig)
else:
    st.info("No sentiment data available.")

# --- PIE CHART ---
def categorize_sentiment(value):
    if value > 0.1:
        return "Positive"
    elif value < -0.1:
        return "Negative"
    else:
        return "Neutral"

st.subheader("🥧 Sentiment Distribution by Category")
for stock in STOCKS:
    st.markdown(f"### {stock}")
    news = stock_news[stock_news['Ticker'] == stock].copy()
    if not news.empty:
        news['Category'] = news['Sentiment'].apply(categorize_sentiment)
        pie_df = news['Category'].value_counts().reset_index()
        pie_df.columns = ['Category', 'Count']
        fig = px.pie(pie_df, names='Category', values='Count', title=f"{stock} Sentiment Breakdown")
        st.plotly_chart(fig)
    else:
        st.warning("No sentiment data to display pie chart.")
