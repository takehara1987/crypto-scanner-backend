### CÓDIGO FINAL E COMPLETO (v57 - PARA RENDER COM SUGESTÃO ELLIOTT) ###

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
import numpy as np
import os

warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)

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

def sugerir_estado_elliott(ticker, interval):
    """Analisa a estrutura de pivôs para sugerir um estado de onda de Elliott."""
    try:
        periodo = "5y" if interval == "1wk" else "2y"
        dados = yf.Ticker(ticker).history(period=periodo, interval=interval)
        if dados.empty or len(dados) < 20: return "Dados Insuficientes"
        
        indices_topos, _ = find_peaks(dados['High'], distance=5, prominence=dados['High'].std()*0.5)
        indices_fundos, _ = find_peaks(-dados['Low'], distance=5, prominence=dados['Low'].std()*0.5)
        
        if len(indices_topos) < 2 or len(indices_fundos) < 2: return "Indefinido / Lateral"

        ultimo_topo = dados['High'].iloc[indices_topos[-1]]; penultimo_topo = dados['High'].iloc[indices_topos[-2]]
        ultimo_fundo = dados['Low'].iloc[indices_fundos[-1]]; penultimo_fundo = dados['Low'].iloc[indices_fundos[-2]]

        if ultimo_topo > penultimo_topo and ultimo_fundo > penultimo_fundo:
            return "Impulso de Alta"
        elif ultimo_topo < penultimo_topo and ultimo_fundo < penultimo_fundo:
            return "Impulso de Baixa"
        else:
            return "Indefinido / Correção"
    except Exception:
        return "Erro na Análise"

def analisar_ativo(ticker):
    """Função principal que faz a análise completa para um único ativo."""
    try:
        dados_d1 = yf.Ticker(ticker).history(period="1y")
        if dados_d1.empty or len(dados_d1) < 201: return None
        
        # --- Cálculo de Indicadores ---
        dados_d1['MME200'] = ta.ema(dados_d1['Close'], length=200)
        dados_d1['Volume_MA20'] = dados_d1['Volume'].rolling(window=20).mean()
        dados_d1['range_low_30d'] = dados_d1['Low'].rolling(window=30).min()
        
        # --- Verificação de Setups no Penúltimo Dia ---
        penultimo_dia = dados_d1.iloc[-2]; antepenultimo_dia = dados_d1.iloc[-3]
        
        # FILTROS
        tendencia_de_alta = penultimo_dia['Close'] > penultimo_dia['MME200']
        btc_em_alta = True
        if ticker != "BTC-USD":
            btc_data = get_btc_data()
            if btc_data is None or btc_data.empty: return None
            btc_no_dia = btc_data.loc[btc_data.index.asof(penultimo_dia.name)]
            btc_em_alta = btc_no_dia['Close'] > btc_no_dia['MME21']

        if tendencia_de_alta and btc_em_alta:
            # Setup: Wyckoff Spring com Volume
            suporte_range = antepenultimo_dia['range_low_30d']
            if antepenultimo_dia['Low'] < suporte_range and penultimo_dia['Close'] > suporte_range and penultimo_dia['Volume'] > penultimo_dia['Volume_MA20']:
                stop_potencial = antepenultimo_dia['Low']
                
                # Se um setup for encontrado, fazemos a análise de Elliott
                print(f"  > Setup encontrado para {ticker}! Realizando análise de contexto Elliott...")
                contexto_elliott = {
                    'Semanal': sugerir_estado_elliott(ticker, "1wk"),
                    'Diário': sugerir_estado_elliott(ticker, "1d"),
                    '1 Hora': sugerir_estado_elliott(ticker, "1h")
                }
                
                return {
                    'ativo': ticker, 
                    'estrategia': 'COMPRA_SPRING',
                    'data_setup': penultimo_dia.name.strftime('%Y-%m-%d'),
                    'stop_potencial': stop_potencial,
                    'contexto_elliott': contexto_elliott
                }
    except Exception:
        return None
    return None

# ==============================================================================
# O PONTO DE ENTRADA DA API (ENDPOINT)
# ==============================================================================
@app.route('/scan', methods=['GET'])
def scan_market():
    """Executa o scanner para a watchlist e retorna os resultados em formato JSON."""
    
    # Watchlist otimizada para o plano gratuito
    watchlist = [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD"
    ]
    
    setups_em_andamento = []
    
    get_btc_data() # Carrega os dados do BTC uma vez
    
    for ativo in watchlist:
        print(f"Analisando {ativo}...")
        resultado = analisar_ativo(ativo)
        if resultado:
            setups_em_andamento.append(resultado)
            
    # Para este exemplo, usamos os setups encontrados como "em andamento"
    return jsonify({
        'sinaisConfirmados': [],
        'setupsEmAndamento': setups_em_andamento,
        'ativosEmObservacao': []
    })

@app.route('/')
def health_check():
    return "Servidor de análise v57 a funcionar!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
