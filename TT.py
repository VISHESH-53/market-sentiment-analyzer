# Quantitative Market Sentiment Analyzer — Final Debugged Version

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

# Validate date range
if END_DATE < START_DATE:
    st.error("Error: End date must be after start date")
    st.stop()

# --- NEWS API KEY ---
NEWS_API_KEY = "85ee2bd2e1154ca9b865f97ebf666a77"
try:
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception as e:
    st.error(f"Failed to initialize News API client: {str(e)}")
    newsapi = None

# --- UTILITY FUNCTIONS ---
def fetch_stock_data(ticker):
    try:
        df = yf.download(ticker, start=START_DATE, end=END_DATE)[['Open', 'High', 'Low', 'Close', 'Volume']]
        df.reset_index(inplace=True)
        df['Ticker'] = ticker
        
        # Data validation
        if df.empty:
            st.warning(f"No data returned for {ticker} in the selected date range")
        elif 'Close' not in df.columns:
            st.error(f"Missing 'Close' column in data for {ticker}")
        elif not pd.api.types.is_numeric_dtype(df['Close']):
            st.error(f"Invalid data type for 'Close' prices in {ticker}")
        
        return df
    except Exception as e:
        st.error(f"Failed to fetch data for {ticker}: {str(e)}")
        return pd.DataFrame()

def fetch_news_sentiment(ticker):
    if not newsapi:
        return pd.DataFrame(columns=['Date', 'Ticker', 'Headline', 'Sentiment'])
    
    try:
        articles = newsapi.get_everything(
            q=f"{ticker} stock",
            language="en",
            sort_by="relevancy",
            from_param=START_DATE,
            to=END_DATE,
            page_size=10
        )
        
        records = []
        for article in articles['articles']:
            try:
                headline = article['title']
                published_at = pd.to_datetime(article['publishedAt']).date()
                sentiment = TextBlob(headline).sentiment.polarity
                records.append({
                    'Date': published_at,
                    'Ticker': ticker,
                    'Headline': headline,
                    'Sentiment': sentiment
                })
            except Exception as e:
                st.warning(f"Error processing article for {ticker}: {str(e)}")
                continue
                
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"News API error for {ticker}: {str(e)}")
        return pd.DataFrame(columns=['Date', 'Ticker', 'Headline', 'Sentiment'])

# --- DATA INGESTION ---
price_frames = []
sentiment_frames = []

with st.spinner("Fetching market data..."):
    for stock in STOCKS:
        stock_df = fetch_stock_data(stock)
        price_frames.append(stock_df)
        
        if newsapi:
            news_df = fetch_news_sentiment(stock)
            sentiment_frames.append(news_df)

# --- COMBINE ALL DATA ---
stock_prices = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame()
stock_news = pd.concat(sentiment_frames, ignore_index=True) if sentiment_frames else pd.DataFrame()

# --- PRICE CHART ---
st.subheader("📉 Stock Closing Prices")
if not stock_prices.empty:
    for stock in STOCKS:
        subset = stock_prices[stock_prices['Ticker'] == stock].copy()
        if not subset.empty:
            try:
                # Convert and validate date column
                subset['Date'] = pd.to_datetime(subset['Date'])
                
                # Validate data before plotting
                if 'Close' not in subset.columns:
                    st.error(f"Missing 'Close' column for {stock}")
                    continue
                    
                if not pd.api.types.is_numeric_dtype(subset['Close']):
                    st.error(f"Invalid data type for 'Close' prices in {stock}")
                    continue
                
                # Create and display plot
                fig = px.line(
                    subset, 
                    x='Date', 
                    y='Close', 
                    title=f"{stock} Closing Price",
                    labels={'Close': 'Price ($)', 'Date': 'Date'}
                )
                fig.update_layout(
                    xaxis_title='Date',
                    yaxis_title='Price ($)',
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error creating chart for {stock}: {str(e)}")
        else:
            st.warning(f"No price data available for {stock}")
else:
    st.error("No stock price data available. Please check your selections and date range.")

# --- NEWS SENTIMENT TABLE ---
if newsapi:
    st.subheader("📰 Latest News Sentiment")
    if not stock_news.empty:
        for stock in STOCKS:
            st.markdown(f"### {stock}")
            news_subset = stock_news[stock_news['Ticker'] == stock]
            if not news_subset.empty:
                st.dataframe(
                    news_subset[['Date', 'Headline', 'Sentiment']]
                    .sort_values('Date', ascending=False)
                    .style.format({'Sentiment': "{:.2f}"})
                )
            else:
                st.info(f"No news data found for {stock}.")
    else:
        st.info("No news sentiment data available.")

# --- AVERAGE SENTIMENT BAR ---
if newsapi and not stock_news.empty:
    st.subheader("📊 Average Sentiment per Stock")
    avg_sentiment = stock_news.groupby("Ticker")["Sentiment"].mean().reset_index()
    if not avg_sentiment.empty:
        fig = px.bar(
            avg_sentiment, 
            x="Ticker", 
            y="Sentiment", 
            color="Ticker", 
            title="Average Sentiment", 
            range_y=[-1, 1],
            labels={'Sentiment': 'Sentiment Score', 'Ticker': 'Stock'}
        )
        fig.update_layout(
            yaxis_title='Sentiment Score',
            xaxis_title='Stock'
        )
        st.plotly_chart(fig, use_container_width=True)

# --- PIE CHART ---
def categorize_sentiment(value):
    if value > 0.1:
        return "Positive"
    elif value < -0.1:
        return "Negative"
    else:
        return "Neutral"

if newsapi and not stock_news.empty:
    st.subheader("🥧 Sentiment Distribution by Category")
    for stock in STOCKS:
        st.markdown(f"### {stock}")
        news = stock_news[stock_news['Ticker'] == stock].copy()
        if not news.empty:
            news['Category'] = news['Sentiment'].apply(categorize_sentiment)
            pie_df = news['Category'].value_counts().reset_index()
            pie_df.columns = ['Category', 'Count']
            fig = px.pie(
                pie_df, 
                names='Category', 
                values='Count', 
                title=f"{stock} Sentiment Breakdown",
                hole=0.3
            )
            st.plotly_chart(fig, use_container_width=True)
