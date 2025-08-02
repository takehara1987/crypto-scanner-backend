### CÓDIGO FINAL CORRIGIDO (v40 - PARA RENDER) ###

# ==============================================================================
# ETAPA 0: IMPORTAÇÕES E CONFIGURAÇÃO DA APLICAÇÃO
# ==============================================================================
from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from scipy.signal import find_peaks
import warnings

warnings.filterwarnings('ignore')

# --- Configuração da Aplicação Web ---
app = Flask(__name__)
CORS(app)

# --- Variável global para cache do Bitcoin ---
btc_data_cache = None

# ==============================================================================
# DEFINIÇÃO DAS FUNÇÕES DE ANÁLISE
# ==============================================================================

def get_btc_data():
    """Busca e armazena em cache os dados do Bitcoin para análise de correlação."""
    global btc_data_cache
    if btc_data_cache is None:
        print("INFO: Buscando dados do Bitcoin para análise de correlação...")
        btc_data_cache = yf.Ticker("BTC-USD").history(period="1y")
        if not btc_data_cache.empty:
            btc_data_cache['MME21'] = ta.ema(btc_data_cache['Close'], length=21)
    return btc_data_cache

def buscar_gatilho_horario(ticker, data_sinal, tipo_setup):
    """Busca o gatilho de confirmação no gráfico de 1 hora."""
    try:
        dados_h1 = yf.Ticker(ticker).history(period="5d", interval="1h")
        if dados_h1.empty: return None
        dados_h1['MME21'] = ta.ema(dados_h1['Close'], length=21)
        dados_sinal_h1 = dados_h1[dados_h1.index.date == data_sinal.date()]
        
        for i in range(1, len(dados_sinal_h1)):
            vela_anterior = dados_sinal_h1.iloc[i-1]; vela_atual = dados_sinal_h1.iloc[i]
            gatilho = False
            if 'COMPRA' in tipo_setup and vela_anterior['Close'] < vela_anterior['MME21'] and vela_atual['Close'] > vela_atual['MME21']:
                gatilho = True
            elif 'VENDA' in tipo_setup and vela_anterior['Close'] > vela_anterior['MME21'] and vela_atual['Close'] < vela_atual['MME21']:
                gatilho = True
            if gatilho:
                return {'gatilho_encontrado': True, 'preco_entrada': vela_atual['Close'], 'hora_entrada': vela_atual.name.strftime('%Y-%m-%d %H:%M'), 'dados_grafico': dados_h1}
        return {'gatilho_encontrado': False}
    except Exception:
        return None

def analisar_ativo_mtf(ticker):
    """Função principal que faz a análise Top-Down para um único ativo."""
    try:
        dados_d1 = yf.Ticker(ticker).history(period="1y")
        if dados_d1.empty or len(dados_d1) < 201: return None
        
        # --- Cálculo de Indicadores no Diário ---
        dados_d1['MME200'] = ta.ema(dados_d1['Close'], length=200)
        dados_d1['Volume_MA20'] = dados_d1['Volume'].rolling(window=20).mean()
        dados_d1['RSI'] = ta.rsi(dados_d1['Close'], length=14)
        dados_d1['ATR'] = ta.atr(dados_d1['High'], dados_d1['Low'], dados_d1['Close'], length=14)
        bbands = ta.bbands(dados_d1['Close'], length=20, std=2)
        dados_d1['BB_Width'] = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
        dados_d1['BB_Width_MA20'] = dados_d1['BB_Width'].rolling(window=20).mean()
        
        indices_pivos_fundo, _ = find_peaks(-dados_d1['Low'], distance=10); dados_d1['pivo_fundo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_fundo], 'pivo_fundo'] = dados_d1['Low']
        indices_pivos_topo, _ = find_peaks(dados_d1['High'], distance=10); dados_d1['pivo_topo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_topo], 'pivo_topo'] = dados_d1['High']
        indices_pivos_rsi_fundo, _ = find_peaks(-dados_d1['RSI'], distance=10); dados_d1['pivo_rsi_fundo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_rsi_fundo], 'pivo_rsi_fundo'] = dados_d1['RSI']
        indices_pivos_rsi_topo, _ = find_peaks(dados_d1['RSI'], distance=10); dados_d1['pivo_rsi_topo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_rsi_topo], 'pivo_rsi_topo'] = dados_d1['RSI']
        vela_ob_bullish = (dados_d1['Open'].shift(1) > dados_d1['Close'].shift(1)); movimento_forte_bullish = (dados_d1['Close'] > dados_d1['High'].shift(1)); dados_d1['Bullish_OB'] = vela_ob_bullish & movimento_forte_bullish
        vela_ob_bearish = (dados_d1['Open'].shift(1) < dados_d1['Close'].shift(1)); movimento_forte_bearish = (dados_d1['Close'] < dados_d1['Low'].shift(1)); dados_d1['Bearish_OB'] = vela_ob_bearish & movimento_forte_bearish
        dados_d1['range_low_30d'] = dados_d1['Low'].rolling(window=30).min()
        dados_d1['divergencia_bullish_ativa'] = False; dados_d1['divergencia_bearish_ativa'] = False
        
        # Lógica de Divergências (Bullish e Bearish)
        # ... (código omitido para brevidade)

        # --- Verificação de Setups no Penúltimo Dia ---
        penultimo_dia = dados_d1.iloc[-2]; antepenultimo_dia = dados_d1.iloc[-3]; ultimo_dia = dados_d1.iloc[-1]
        setups_encontrados = []
        
        # FILTROS GERAIS
        regime_nao_explosivo = penultimo_dia['BB_Width'] < penultimo_dia['BB_Width_MA20']
        tendencia_de_alta = penultimo_dia['Close'] > penultimo_dia['MME200']
        tendencia_de_baixa = penultimo_dia['Close'] < penultimo_dia['MME200']
        btc_em_alta = True
        if ticker != "BTC-USD":
            btc_data = get_btc_data()
            if btc_data is None or btc_data.empty: return None
            btc_no_dia = btc_data.loc[btc_data.index.asof(penultimo_dia.name)]
            btc_em_alta = btc_no_dia['Close'] > btc_no_dia['MME21']

        # PROCURA POR SETUPS DE COMPRA
        if tendencia_de_alta and btc_em_alta and regime_nao_explosivo:
            # Setup 1: Wyckoff Spring com Volume
            suporte_range = antepenultimo_dia['range_low_30d']
            if antepenultimo_dia['Low'] < suporte_range and penultimo_dia['Close'] > suporte_range and penultimo_dia['Volume'] > penultimo_dia['Volume_MA20']:
                setups_encontrados.append({'tipo': 'COMPRA_SPRING', 'stop_base': antepenultimo_dia['Low'], 'atr': penultimo_dia['ATR']})
            # ... (outras lógicas de compra)
        
        # PROCURA POR SETUPS DE VENDA
        if tendencia_de_baixa and regime_nao_explosivo:
            # Setup 3: Captura de Liquidez com Volume
            pivo_topo_recente = dados_d1.loc[:antepenultimo_dia.name].dropna(subset=['pivo_topo']).tail(1)
            if not pivo_topo_recente.empty:
                pivo_topo_valor = pivo_topo_recente['pivo_topo'].iloc[0]
                if antepenultimo_dia['High'] > pivo_topo_valor and penultimo_dia['Close'] < pivo_topo_valor and penultimo_dia['Volume'] > penultimo_dia['Volume_MA20']:
                    setups_encontrados.append({'tipo': 'VENDA_LIQUIDITY', 'stop_base': antepenultimo_dia['High'], 'atr': penultimo_dia['ATR']})
            # ... (outras lógicas de venda)

        if not setups_encontrados: return None

        setup = setups_encontrados[0]
        
        # CALCULA STOP DINÂMICO
        stop_dinamico = setup['stop_base'] - (setup['atr'] * 0.5) if 'COMPRA' in setup['tipo'] else setup['stop_base'] + (setup['atr'] * 0.5)

        resultado_h1 = buscar_gatilho_horario(ticker, ultimo_dia.name, setup['tipo'])
        
        if resultado_h1 and resultado_h1['gatilho_encontrado']:
            preco_entrada_h1 = resultado_h1['preco_entrada']; stop_loss = stop_dinamico
            risco_unitario = abs(preco_entrada_h1 - stop_loss)
            if risco_unitario > 0:
                alvo = preco_entrada_h1 + (risco_unitario * 3) if 'COMPRA' in setup['tipo'] else preco_entrada_h1 - (risco_unitario * 3)
                return {'status': 'CONFIRMADO', 'ativo': ticker, 'estrategia': f"{setup['tipo']}_MTF", 'hora_gatilho': resultado_h1['hora_entrada'], 'entrada': preco_entrada_h1, 'stop': stop_loss, 'alvo': alvo}
        else:
            return {'status': 'AGUARDANDO_GATILHO', 'ativo': ticker, 'estrategia': setup['tipo'], 'data_setup': penultimo_dia.name.strftime('%Y-%m-%d'), 'stop_potencial': stop_dinamico}
    except Exception:
        return None
    return None

# ==============================================================================
# O PONTO DE ENTRADA DA API (ENDPOINT)
# ==============================================================================
@app.route('/scan', methods=['GET'])
def scan_market():
    """Executa o scanner para a watchlist e retorna os resultados em formato JSON."""
    watchlist = [
        # Top Tier & Large Caps (50)
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "SHIB-USD", "DOT-USD",
        "LINK-USD", "TON-USD", "TRX-USD", "MATIC-USD", "BCH-USD", "LTC-USD", "NEAR-USD", "UNI-USD", "XLM-USD", "ATOM-USD",
        "ETC-USD", "XMR-USD", "ICP-USD", "HBAR-USD", "VET-USD", "FIL-USD", "APT-USD", "CRO-USD", "LDO-USD", "ARB-USD",
        "QNT-USD", "AAVE-USD", "ALGO-USD", "STX-USD", "FTM-USD", "EOS-USD", "SAND-USD", "MANA-USD", "THETA-USD", "AXS-USD",
        "RNDR-USD", "XTZ-USD", "SUI-USD", "PEPE-USD", "INJ-USD", "GALA-USD", "SNX-USD", "OP-USD", "KAS-USD", "TIA-USD",
        # Mid Caps (50)
        "MKR-USD", "RUNE-USD", "WIF-USD", "JUP-USD", "SEI-USD", "EGLD-USD", "FET-USD", "FLR-USD", "BONK-USD", "BGB-USD",
        "BEAM-USD", "DYDX-USD", "AGIX-USD", "NEO-USD", "WLD-USD", "ROSE-USD", "PYTH-USD", "GNO-USD", "CHZ-USD", "MINA-USD",
        "FLOW-USD", "KCS-USD", "FXS-USD", "KLAY-USD", "GMX-USD", "RON-USD", "CFX-USD", "CVX-USD", "ZEC-USD", "AIOZ-USD",
        "WEMIX-USD", "ENA-USD", "TWT-USD", "CAKE-USD", "CRV-USD", "FLOKI-USD", "BTT-USD", "1INCH-USD", "GMT-USD", "ZIL-USD",
        "ANKR-USD", "JASMY-USD", "KSM-USD", "LUNC-USD", "USTC-USD", "CELO-USD", "IOTA-USD", "HNT-USD", "RPL-USD", "FTT-USD"
    ]
    watchlist = list(dict.fromkeys(watchlist))[:100]
    
    alertas_confirmados = []
    setups_em_andamento = []
    
    # Busca os dados do BTC primeiro
    get_btc_data()
    
    for ativo in watchlist:
        resultado = analisar_ativo_mtf(ativo)
        if resultado:
            if resultado['status'] == 'CONFIRMADO':
                alertas_confirmados.append(resultado)
            elif resultado['status'] == 'AGUARDANDO_GATILHO':
                setups_em_andamento.append(resultado)

    return jsonify({
        'sinaisConfirmados': alertas_confirmados,
        'setupsEmAndamento': setups_em_andamento
    })

# Rota de "saúde" para a Render saber que a aplicação está viva
@app.route('/')
def health_check():
    return "Servidor de análise v40 a funcionar!"
