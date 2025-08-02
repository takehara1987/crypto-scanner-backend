# Salve este ficheiro como "app.py"

from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings

warnings.filterwarnings('ignore')

# --- Configuração da Aplicação Web ---
app = Flask(__name__)
CORS(app)

# --- A nossa função de análise (simplificada para um exemplo rápido) ---
def analisar_ativo_simplificado(ticker):
    """Analisa um único ativo à procura de um setup de Wyckoff Spring."""
    try:
        dados_d1 = yf.Ticker(ticker).history(period="1y")
        if dados_d1.empty or len(dados_d1) < 32: return None
        
        dados_d1['range_low_30d'] = dados_d1['Low'].rolling(window=30).min()
        
        penultimo_dia = dados_d1.iloc[-2]
        antepenultimo_dia = dados_d1.iloc[-3]
        
        suporte_range = antepenultimo_dia['range_low_30d']
        
        # Condição do Spring no Diário
        if antepenultimo_dia['Low'] < suporte_range and penultimo_dia['Close'] > suporte_range:
            stop_loss = antepenultimo_dia['Low']
            return {
                'ativo': ticker, 
                'estrategia': 'COMPRA_SPRING',
                'data_setup': penultimo_dia.name.strftime('%Y-%m-%d'),
                'stop_potencial': stop_loss
            }
    except Exception:
        return None
    return None

# --- O Ponto de Entrada da API (Endpoint) ---
@app.route('/scan', methods=['GET'])
def scan_market():
    """Executa o scanner para a watchlist e retorna os resultados em formato JSON."""
    watchlist = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "LINK-USD", "DOT-USD", "AVAX-USD"]
    
    setups_em_andamento = []
    
    for ativo in watchlist:
        resultado = analisar_ativo_simplificado(ativo)
        if resultado:
            setups_em_andamento.append(resultado)
            
    mock_sinais_confirmados = [
        { 'ativo': 'SOL-USD', 'estrategia': 'COMPRA_SPRING_MTF', 'hora_gatilho': '2025-08-01 14:00', 'entrada': 145.50, 'stop': 138.20, 'alvo': 167.10 }
    ]

    return jsonify({
        'sinaisConfirmados': mock_sinais_confirmados,
        'setupsEmAndamento': setups_em_andamento
    })

# Rota de "saúde" para a Render saber que a aplicação está viva
@app.route('/')
def health_check():
    return "Servidor de análise a funcionar!"

# A Render usa um servidor de produção como o Gunicorn, por isso não precisamos do app.run()
