import yfinance as yf
import pandas as pd
from textblob import TextBlob
import sqlalchemy
from datetime import datetime, timedelta
import streamlit as st
from newsapi import NewsApiClient
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="📈 Market Sentiment Analyzer", layout="wide")

# --- Sidebar Inputs ---
STOCKS = st.sidebar.multiselect("Select stocks:", ['AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN'], default=['AAPL'])
START_DATE = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
END_DATE = st.sidebar.date_input("End Date", datetime.now())

# --- Database Setup ---
DB_URI = 'sqlite:///stock_analysis.db'
engine = sqlalchemy.create_engine(DB_URI)

# --- Reset old tables to avoid schema mismatch ---
with engine.connect() as conn:
    conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS stock_prices"))
    conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS stock_news"))

# --- NewsAPI Setup ---
newsapi = NewsApiClient(api_key='85ee2bd2e1154ca9b865f97ebf666a77')

# --- Functions ---
def fetch_stock_data(ticker):
    data = yf.download(ticker, start=START_DATE, end=END_DATE)
    data.reset_index(inplace=True)
    data['Ticker'] = ticker
    return data

def fetch_real_news(ticker):
    try:
        articles = newsapi.get_everything(q=f"{ticker} stock", language='en', sort_by='relevancy', page_size=5)
        headlines = [article['title'] for article in articles['articles']]
        sentiments = [TextBlob(h).sentiment.polarity for h in headlines]
        return pd.DataFrame({'Ticker': ticker, 'Headline': headlines, 'Sentiment': sentiments})
    except:
        return pd.DataFrame(columns=['Ticker', 'Headline', 'Sentiment'])

def store_to_db(df, table_name):
    df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')

# --- Main Execution ---
all_data, all_sentiment = [], []

for stock in STOCKS:
    df = fetch_stock_data(stock)
    all_data.append(df)
    store_to_db(df, 'stock_prices')

    news_df = fetch_real_news(stock)
    all_sentiment.append(news_df)
    store_to_db(news_df, 'stock_news')

# --- Load from DB ---
stock_prices = pd.read_sql("SELECT * FROM stock_prices", engine)
stock_news = pd.read_sql("SELECT * FROM stock_news", engine)

# --- Price Chart ---
st.title("📊 Quantitative Market Sentiment Analyzer")
st.subheader("Stock Prices Over Time")
for stock in STOCKS:
    subset = stock_prices[stock_prices['Ticker'] == stock]
    if not subset.empty:
        subset['Date'] = pd.to_datetime(subset['Date'])
        fig = px.line(subset, x='Date', y='Close', title=f"{stock} Closing Price")
        st.plotly_chart(fig)

# --- Sentiment Analysis ---
st.subheader("Sentiment Analysis of Latest News")
for stock in STOCKS:
    st.markdown(f"**{stock}**")
    news = stock_news[stock_news['Ticker'] == stock][['Headline', 'Sentiment']]
    st.dataframe(news)
    if not news.empty:
        fig = px.bar(news, x='Headline', y='Sentiment', title=f"{stock} News Sentiment")
        st.plotly_chart(fig)

# --- Average Sentiment Chart ---
st.subheader("📌 Average Sentiment per Stock")
avg_sentiment = stock_news.groupby("Ticker")["Sentiment"].mean().reset_index()
fig = px.bar(avg_sentiment, x='Ticker', y='Sentiment', color='Ticker', title="Average Sentiment")
st.plotly_chart(fig)

# --- Pie Chart of Sentiment Categories ---
st.subheader("🥧 Sentiment Category Distribution")
def categorize(p):
    if p > 0.1:
        return "Positive"
    elif p < -0.1:
        return "Negative"
    else:
        return "Neutral"

for stock in STOCKS:
    st.markdown(f"**{stock}**")
    news = stock_news[stock_news['Ticker'] == stock]
    news = news.dropna(subset=['Sentiment'])
    news['Category'] = news['Sentiment'].apply(categorize)
    pie_data = news['Category'].value_counts().reset_index()
    pie_data.columns = ['Sentiment', 'Count']
    fig = px.pie(pie_data, names='Sentiment', values='Count', title=f"{stock} Sentiment Distribution")
    st.plotly_chart(fig)
