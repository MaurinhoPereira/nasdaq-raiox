import streamlit as st
from streamlit_autorefresh import st_autorefresh
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st_autorefresh(interval=15000, key="refresh")

# =========================
# CSS
# =========================
st.markdown("""
<style>
html, body, .stApp {background:black;color:white;}
.block-container {padding-top:0rem;}
header, footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================
col_top1, col_top2, col_top3, col_top4 = st.columns([4,3,1.5,1.5])

# TÍTULO
with col_top1:
    st.markdown("""
    <div style='display:flex;flex-direction:column;justify-content:center;'>
        <span style='color:#4DA3FF;font-size:40px;font-weight:bold;'>NASDAQ RAIO X</span>
        <span style='color:#888;font-size:25px;'>Maurinho.Trader</span>
    </div>
    """, unsafe_allow_html=True)

# SENTIMENTO (container vazio)
with col_top2:
    sentiment_box = st.empty()

# ATIVO
with col_top3:
    ticker_symbol = st.selectbox(
        "Ativo",
        ["^NDX","QQQ"],
        label_visibility="collapsed"
    )

# VENCIMENTO + FONTE (🔥 ADIÇÃO AQUI, sem mexer no resto)
with col_top4:
    data_source = st.selectbox(
        "Fonte",
        ["Yahoo", "Tradier"],
        label_visibility="collapsed"
    )

    ticker = yf.Ticker(ticker_symbol)

    selected_exp = st.selectbox(
        "Venc",
        ticker.options,
        label_visibility="collapsed"
    )

# =========================
# DADOS (YAHOO / TRADIER HOOK)
# =========================

# 🔵 YAHOO (ATUAL)
if data_source == "Yahoo":
    opt = ticker.option_chain(selected_exp)
    calls = opt.calls
    puts = opt.puts

# 🟠 TRADIER (PLACEHOLDER - ainda não conectado)
else:
    # mantém estrutura igual pra não quebrar o sistema
    opt = ticker.option_chain(selected_exp)
    calls = opt.calls
    puts = opt.puts

price = ticker.history(period="1d")["Close"].iloc[-1]

# =========================
# HISTÓRICO (REAÇÃO + FILTRO)
# =========================
hist = ticker.history(period="1d", interval="5m")

if hist.index.tz is not None:
    hist = hist.tz_convert(None)

hist = hist.between_time("09:30", "16:00")

prev_price = hist["Close"].iloc[-2] if len(hist) > 2 else price

# =========================
# FLOW
# =========================
calls["flow"] = calls["volume"].fillna(0)+calls["openInterest"].fillna(0)
puts["flow"] = puts["volume"].fillna(0)+puts["openInterest"].fillna(0)

flow_df = pd.DataFrame({
    "Calls": calls.groupby("strike")["flow"].sum(),
    "Puts": puts.groupby("strike")["flow"].sum()
}).fillna(0)

# =========================
# GEX
# =========================
calls["gex"] = calls["openInterest"]*calls["impliedVolatility"]*calls["strike"]
puts["gex"] = -puts["openInterest"]*puts["impliedVolatility"]*puts["strike"]

gex_df = pd.concat([
    calls[["strike","gex"]],
    puts[["strike","gex"]]
]).groupby("strike")["gex"].sum().to_frame()

# =========================
# FILTRO
# =========================
range_points = 700
df = flow_df.join(gex_df, how="outer").fillna(0)
df = df[(df.index > price-range_points)&(df.index < price+range_points)]

# GARANTIR DADOS VISÍVEIS
df = df[(df["Calls"] > 0) | (df["Puts"] > 0)]

# WALLS
call_wall = df["Calls"].idxmax()
put_wall = df["Puts"].idxmax()

# NÍVEIS INSTITUCIONAIS
flow_inst = df[(df["Calls"] > df["Calls"].max()*0.7) | (df["Puts"] > df["Puts"].max()*0.7)].index
gex_inst = df[df["gex"].abs() > df["gex"].abs().max()*0.6].index

# =========================
# SENTIMENTO
# =========================
flow_pct = (df["Calls"].sum()-df["Puts"].sum())/(df["Calls"].sum()+df["Puts"].sum()+1e-9)*100
gex_pct = df["gex"].sum()/(df["gex"].abs().sum()+1e-9)*100

if flow_pct>10 and gex_pct>10:
    sentiment="🟦 Tendência Controlada"; color="#3FA2FF"
elif flow_pct>10 and gex_pct<-10:
    sentiment="🚀 Aceleração Alta"; color="#00FF88"
elif flow_pct<-10 and gex_pct>10:
    sentiment="📉 Travado"; color="#FFB347"
elif flow_pct<-10 and gex_pct<-10:
    sentiment="🔻 Aceleração Queda"; color="#FF3B3B"
else:
    sentiment="⚪ Neutro"; color="#AAA"

# ALERTA REGIME
if "last_regime" not in st.session_state:
    st.session_state["last_regime"]=sentiment

if sentiment!=st.session_state["last_regime"]:
    st.warning(f"⚠️ {st.session_state['last_regime']} ➜ {sentiment}")
    st.markdown("""<audio autoplay>
    <source src="https://www.soundjay.com/buttons/sounds/button-3.mp3">
    </audio>""", unsafe_allow_html=True)

st.session_state["last_regime"]=sentiment

# DISPLAY (TOPO)
sentiment_box.markdown(f"""
<div style='background:#111;padding:6px 10px;border-radius:6px;text-align:center;width:fit-content;'>
<b style='color:{color};font-size:16px'>{sentiment}</b><br>
<span style='color:#888;font-size:12px'>Flow {flow_pct:+.1f}% | GEX {gex_pct:+.1f}%</span>
</div>
""", unsafe_allow_html=True)

# =========================
# REAÇÃO
# =========================
reactions=[]

def check(level,name):
    dist = price - level

    if prev_price < level and price > level:
        reactions.append(f"🚀 Rompeu ↑ {name} ({int(level)}) | +{int(abs(dist))} pts")

    elif prev_price > level and price < level:
        reactions.append(f"🔻 Rompeu ↓ {name} ({int(level)}) | -{int(abs(dist))} pts")

    elif abs(dist) < 20:
        reactions.append(f"⚠️ Rejeição em {name} ({int(level)})")

check(call_wall,"CALL WALL")
check(put_wall,"PUT WALL")

for lvl in flow_inst:
    check(lvl,"FLOW INST")

for lvl in gex_inst:
    check(lvl,"GEX INST")

if reactions:
    for r in reactions:
        st.info(r)

    st.markdown("""
<script>
var audio = new Audio("https://www.soundjay.com/buttons/sounds/button-09.mp3");
audio.play();
</script>
""", unsafe_allow_html=True)

# =========================
# NORMALIZAÇÃO
# =========================
max_total = max(df["Calls"].max(), df["Puts"].max())

df["Calls_norm"] = df["Calls"] / max_total
df["Puts_norm"] = -(df["Puts"] / max_total)
df["gex_norm"]=df["gex"]/df["gex"].abs().max()

# CORES
top_calls=df.nlargest(3,"Calls").index
top_puts=df.nlargest(3,"Puts").index
call_colors=["#00FF00" if i in top_calls else "#00FF88" for i in df.index]
put_colors=["#FF0000" if i in top_puts else "#FF3B3B" for i in df.index]

col1,col2=st.columns(2)

# FLOW
with col1:
    fig=go.Figure()
    fig.add_bar(y=df.index,x=df["Calls_norm"],orientation='h',marker_color=call_colors,name="Calls")
    fig.add_bar(y=df.index,x=df["Puts_norm"],orientation='h',marker_color=put_colors,name="Puts")

    fig.add_hline(y=price,line_dash="dot",line_color="white")
    fig.add_annotation(x=1,y=price,xref="paper",yref="y",text=str(round(price)),yshift=10,showarrow=False)

    fig.add_scatter(x=[0],y=[call_wall],mode="markers",marker=dict(size=8,color="green"), name="Call Wall")
    fig.add_scatter(x=[0],y=[put_wall],mode="markers",marker=dict(size=8,color="red"), name="Put Wall")

    first = True
    for lvl in flow_inst:
        fig.add_scatter(
            x=[0],y=[lvl],
            mode="markers",
            marker=dict(size=6,color="#00FFFF"),
            name="Flow Inst" if first else None,
            showlegend=first
        )
        first = False

    fig.update_layout(
        plot_bgcolor="black",
        paper_bgcolor="black",
        font_color="white",
        title="Flow"
    )

    st.plotly_chart(fig,use_container_width=True)

# GEX
with col2:
    fig=go.Figure()
    colors=["#0052FF" if v>0 else "#FF5A00" for v in df["gex"]]

    fig.add_bar(
        y=df.index,
        x=df["gex_norm"],
        orientation='h',
        marker_color=colors,
        name="GEX"
    )

    fig.add_hline(y=price,line_dash="dot",line_color="white")
    fig.add_annotation(x=1,y=price,xref="paper",yref="y",text=str(round(price)),yshift=10,showarrow=False)

    fig.add_scatter(x=[0],y=[call_wall],mode="markers",marker=dict(size=8,color="green"), name="Call Wall")
    fig.add_scatter(x=[0],y=[put_wall],mode="markers",marker=dict(size=8,color="red"), name="Put Wall")

    first = True
    for lvl in gex_inst:
        fig.add_scatter(
            x=[0],y=[lvl],
            mode="markers",
            marker=dict(size=6,color="#FFD700"),
            name="GEX Inst" if first else None,
            showlegend=first
        )
        first = False

    fig.update_layout(
        plot_bgcolor="black",
        paper_bgcolor="black",
        font_color="white",
        title="GEX"
    )

    st.plotly_chart(fig,use_container_width=True)

# =========================
# PREÇO COM ZONAS
# =========================
st.markdown("### 📈 Movimento do Preço (Intraday)")

price_fig = go.Figure()
price_series = hist["Close"]

flow_zones = set(flow_inst)
gex_zones = set(gex_inst)
zone_threshold = 20

def get_color(p):
    for lvl in gex_zones:
        if abs(p - lvl) < zone_threshold:
            return "#0052FF"
    for lvl in flow_zones:
        if abs(p - lvl) < zone_threshold:
            return "#00FF88"

    if "Alta" in sentiment:
        return "#00FF88"
    elif "Queda" in sentiment:
        return "#FF3B3B"
    elif "Travado" in sentiment:
        return "#FFB347"
    else:
        return "white"

segments=[]
cx,cy=[],[]
prev_color=get_color(price_series.iloc[0])

for i in range(len(price_series)):
    p=price_series.iloc[i]
    t=price_series.index[i]
    c=get_color(p)

    if c!=prev_color and len(cx)>0:
        segments.append((cx,cy,prev_color))
        cx,cy=[],[]

    cx.append(t)
    cy.append(p)
    prev_color=c

if cx:
    segments.append((cx,cy,prev_color))

for x,y,c in segments:
    price_fig.add_trace(go.Scatter(x=x,y=y,mode="lines",line=dict(color=c,width=2)))

price_fig.update_layout(
    plot_bgcolor="black",
    paper_bgcolor="black",
    font_color="white",
    height=400,
    xaxis=dict(type="category")
)

st.plotly_chart(price_fig,use_container_width=True)

# =========================
# EXPLICAÇÃO OPERACIONAL
# =========================
with st.expander("📊 Leitura Operacional + Cenários"):

    st.markdown(f"""
### 🧠 Estado Atual
**{sentiment}**

- Flow: {flow_pct:+.1f}%
- GEX: {gex_pct:+.1f}%

---

### 📊 Interpretação

• Flow forte → presença institucional  
• GEX positivo → mercado tende a travar  
• GEX negativo → mercado tende a acelerar  

---

### 🎯 Possíveis Cenários

""")

    if "Aceleração Alta" in sentiment:
        st.markdown("""
🚀 **Cenário: Continuação de Alta**
- Buscar rompimentos
- Evitar contra tendência
- Alvos mais longos
""")

    elif "Aceleração Queda" in sentiment:
        st.markdown("""
🔻 **Cenário: Continuação de Queda**
- Priorizar vendas
- Pullbacks são oportunidades
- Mercado tende a expandir
""")

    elif "Travado" in sentiment:
        st.markdown("""
📉 **Cenário: Mercado Preso**
- Evitar rompimentos
- Operar extremos (reversão)
- Stops curtos
""")

    elif "Tendência Controlada" in sentiment:
        st.markdown("""
🟦 **Cenário: Tendência Controlada**
- Movimento direcional com pausas
- Boa para parciais
- Atenção às zonas de GEX
""")

    else:
        st.markdown("""
⚪ **Cenário: Neutro**
- Mercado indefinido
- Evitar agressividade
- Esperar confirmação
""")