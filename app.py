import streamlit as st
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

st.set_page_config(page_title="PriceDrop AI", page_icon="💰", layout="wide")
st.title("💰 PriceDrop AI")
st.caption("Simulate price history for any product and get AI buy/wait recommendations.")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

def simulate_price_history(product, base_price, days=90):
    np.random.seed(hash(product) % 1000)
    prices = [base_price]
    for i in range(1, days):
        # Random walk with mean reversion
        drift = 0.001
        vol = 0.015
        shock = np.random.normal(drift, vol)
        # Occasional sale events
        if random.random() < 0.05:
            shock -= random.uniform(0.05, 0.20)
        # Reversion to mean
        reversion = (base_price - prices[-1]) / base_price * 0.05
        new_price = prices[-1] * (1 + shock + reversion)
        new_price = max(new_price, base_price * 0.5)
        prices.append(round(new_price, 2))
    dates = [datetime.today() - timedelta(days=days-i) for i in range(days)]
    return pd.DataFrame({'date': dates, 'price': prices})

def get_recommendation(product, current_price, min_price, max_price, avg_price, trend, gemini_key):
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"""You are a price analyst AI. Analyze this product pricing and give a recommendation.

Product: {product}
Current Price: Rs.{current_price:,.0f}
90-day Minimum: Rs.{min_price:,.0f}
90-day Maximum: Rs.{max_price:,.0f}
90-day Average: Rs.{avg_price:,.0f}
Price vs Average: {((current_price-avg_price)/avg_price*100):+.1f}%
Trend: {trend}

Respond EXACTLY:
VERDICT: [BUY NOW / WAIT / WATCH]
DEAL_SCORE: [1-10]
REASON: [2 sentences explaining your recommendation]
BEST_TIME: [When to buy if waiting — e.g., "Wait for next sale, likely in 2-3 weeks" or "Buy now, prices rising"]
SAVING_TIP: [One specific tip to save more money on this product]"""
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            return f"API_ERROR: {e}"
    else:
        pct = (current_price - avg_price) / avg_price * 100
        if pct < -10:
            return f"VERDICT: BUY NOW\nDEAL_SCORE: 8\nREASON: Current price is {abs(pct):.0f}% below the 90-day average — this is a good deal. Historically this product rarely drops much lower.\nBEST_TIME: Buy within the next 48 hours before price recovers.\nSAVING_TIP: Check if a cashback offer applies via your credit card or payment app."
        elif pct > 10:
            return f"VERDICT: WAIT\nDEAL_SCORE: 3\nREASON: Current price is {pct:.0f}% above average — you're overpaying right now. Prices have dropped before and likely will again.\nBEST_TIME: Wait 2-3 weeks. Sales events typically bring prices back to average.\nSAVING_TIP: Add to wishlist and set a price alert. Avoid impulse buying at peak price."
        else:
            return f"VERDICT: WATCH\nDEAL_SCORE: 5\nREASON: Price is near the 90-day average — neither a great deal nor overpriced. Acceptable if you need it urgently.\nBEST_TIME: Monitor for a further 5-10% drop before committing.\nSAVING_TIP: Check competitor stores for the same product — price differences can be significant."

def parse_rec(text):
    result = {}
    for k in ['VERDICT','DEAL_SCORE','REASON','BEST_TIME','SAVING_TIP']:
        for line in text.split('\n'):
            if line.startswith(k+':'):
                result[k] = line[len(k)+1:].strip()
    return result

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("Track a Product")
    product = st.text_input("Product Name", "iPhone 15 Pro 256GB")
    base_price = st.number_input("Current/Base Price (Rs.)", min_value=100, max_value=500000,
                                  value=119900, step=100)
    category = st.selectbox("Category", ["Smartphones", "Laptops", "Appliances",
                                          "Fashion", "Books", "Electronics", "Other"])
    
    if not GEMINI_KEY:
        key_in = st.text_input("Gemini API Key (optional)", type="password")
        active_key = key_in
    else:
        active_key = GEMINI_KEY
    
    analyze_btn = st.button("Analyze Price", type="primary")

with col2:
    if analyze_btn:
        with st.spinner("Generating price history and analysis..."):
            df = simulate_price_history(product, base_price)
            current = df['price'].iloc[-1]
            min_p = df['price'].min()
            max_p = df['price'].max()
            avg_p = df['price'].mean()
            recent_trend = "rising" if df['price'].iloc[-7:].mean() > df['price'].iloc[-30:-7].mean() else "falling"
            
            raw = get_recommendation(product, current, min_p, max_p, avg_p, recent_trend, active_key)
            rec = parse_rec(raw)
        
        # Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['date'], y=df['price'],
            mode='lines', name='Price', line=dict(color='#00d4ff', width=2)))
        fig.add_hline(y=avg_p, line_dash='dash', line_color='#ffc107',
                      annotation_text=f"Avg Rs.{avg_p:,.0f}")
        fig.add_hline(y=min_p, line_dash='dot', line_color='#00c853',
                      annotation_text=f"Min Rs.{min_p:,.0f}")
        fig.update_layout(
            title=f"{product} — 90 Day Price History",
            xaxis_title="Date", yaxis_title="Price (Rs.)",
            template='plotly_dark', height=300,
            margin=dict(l=10,r=10,t=40,b=10)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Metrics
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Current", f"Rs.{current:,.0f}")
        m2.metric("90d Min", f"Rs.{min_p:,.0f}")
        m3.metric("90d Avg", f"Rs.{avg_p:,.0f}", delta=f"{((current-avg_p)/avg_p*100):+.1f}%")
        m4.metric("Trend", recent_trend.upper())
        
        # Verdict
        verdict = rec.get('VERDICT','WATCH')
        score = rec.get('DEAL_SCORE','5')
        colors = {'BUY NOW':'success','WAIT':'error','WATCH':'warning'}
        getattr(st, colors.get(verdict,'info'))(f"**Verdict: {verdict}  |  Deal Score: {score}/10**")
        st.write("**Analysis:**", rec.get('REASON',''))
        st.write("**Best time to buy:**", rec.get('BEST_TIME',''))
        st.info(f"Saving tip: {rec.get('SAVING_TIP','')}")

st.caption("Puru Mehra | github.com/purumehra1/pricedrop-ai")
