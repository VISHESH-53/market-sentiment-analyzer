# 📈 Quantitative Market Sentiment Analyzer

A Streamlit-based dashboard that visualizes stock prices and performs sentiment analysis on real-time news using NewsAPI and TextBlob.

## Features
- Interactive selection of stocks and date range
- Fetches historical stock prices using `yfinance`
- Performs sentiment analysis on recent news articles
- Visualizes trends using Plotly charts
- Stores and reads data from MySQL database
- Scheduled updates using `schedule`

## Technologies
- Python, Streamlit, yfinance, NewsAPI, TextBlob, MySQL, Plotly, SQLAlchemy

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run TT.py
```

## License
MIT
