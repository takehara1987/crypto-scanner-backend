# Salve este ficheiro como "scanner_telegram.py"

import yfinance as yf
import pandas as pd
import pandas_ta as ta
from scipy.signal import find_peaks
import warnings
import sys
import requests
from datetime import datetime
import numpy as np

warnings.filterwarnings('ignore')

# As chaves secretas serão passadas como argumentos
try:
    BOT_TOKEN = sys.argv[1]
    CHAT_ID = sys.argv[2]
except IndexError:
    print("ERRO: BOT_TOKEN e CHAT_ID devem ser fornecidos como argumentos.")
    sys.exit(1)

btc_data_cache = None

def send_telegram_message(message):
    """Envia uma mensagem para o bot do Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload)
        print("INFO: Mensagem enviada para o Telegram com sucesso.")
    except Exception as e:
        print(f"ERRO: Falha ao enviar mensagem para o Telegram: {e}")

def get_btc_data():
    global btc_data_cache
    if btc_data_cache is None:
        print("INFO: Buscando dados do Bitcoin...")
        btc_data_cache = yf.Ticker("BTC-USD").history(period="1y")
        if not btc_data_cache.empty:
            btc_data_cache['MME21'] = ta.ema(btc_data_cache['Close'], length=21)
    return btc_data_cache

def analisar_ativo(ticker):
    """Função de análise completa para um único ativo."""
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
                return {'ativo': ticker, 'estrategia': 'COMPRA_SPRING', 'stop_potencial': stop_potencial}
    except Exception:
        return None
    return None

def main():
    """Função principal que executa o scanner e envia os alertas."""
    watchlist = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "SHIB-USD", "DOT-USD",
        "LINK-USD", "TON-USD", "TRX-USD", "MATIC-USD", "BCH-USD", "LTC-USD", "NEAR-USD", "UNI-USD", "XLM-USD", "ATOM-USD"
    ]
    
    start_time = datetime.now()
    print(f"Iniciando scanner em {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    setups_encontrados = []
    get_btc_data() # Carrega os dados do BTC uma vez
    
    for ativo in watchlist:
        print(f"Analisando {ativo}...")
        resultado = analisar_ativo(ativo)
        if resultado:
            setups_encontrados.append(resultado)
            
    end_time = datetime.now()
    duration = end_time - start_time
    
    # --- Montagem do Relatório Final para o Telegram ---
    if setups_encontrados:
        message = f"*{len(setups_encontrados)} Setup(s) Diário(s) Encontrado(s)*\n\n"
        for setup in setups_encontrados:
            message += f"*{setup['ativo']}* | `{setup['estrategia']}`\n"
            message += f"  - Stop de Referência: `{setup['stop_potencial']:.4f}`\n\n"
        message += f"_Scanner concluído em {duration.seconds} segundos._"
        send_telegram_message(message)
    else:
        message = f"Nenhum setup novo encontrado na sua watchlist.\n_Scanner concluído em {duration.seconds} segundos._"
        send_telegram_message(message)
        
    print("\n--- FIM DA EXECUÇÃO ---")
    print(message)

if __name__ == "__main__":
    main()
