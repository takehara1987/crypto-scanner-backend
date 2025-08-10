# Nome do arquivo: scanner_render.py
import os
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from scipy.signal import find_peaks
import warnings
from telegram import Bot

warnings.filterwarnings('ignore')

# ==============================================================================
# ETAPA 0: CONFIGURAÇÃO DAS NOTIFICAÇÕES E FUNÇÕES
# ==============================================================================

# Pega as credenciais do Telegram das variáveis de ambiente do Render
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def enviar_mensagem_telegram(mensagem):
    """Envia uma mensagem formatada para o Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRO: Credenciais do Telegram não configuradas nas variáveis de ambiente.")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=mensagem,
            parse_mode='Markdown'
        )
        print(f"Mensagem enviada para o Telegram.")
    except Exception as e:
        print(f"ERRO ao enviar mensagem para o Telegram: {e}")

def formatar_mensagem(resultados, titulo):
    """Formata uma lista de resultados em uma única mensagem para o Telegram."""
    if not resultados:
        # Não envia mensagem se não houver sinais para a categoria
        print(f"Nenhum sinal encontrado para: {titulo}")
        return None

    mensagem = f"*{titulo}*\n\n"
    for r in resultados:
        if r['status'] == 'AGUARDANDO_GATILHO':
             mensagem += (
                f"`{r['ativo']}` | *{r['estrategia']} (Score: {r['score']})*\n"
                f"Data: {r['data_setup']}\n"
                f"Stop Potencial: `{r['stop_potencial']:.5f}`\n"
                "------------------------------------\n"
            )
        elif r['status'] == 'EM_OBSERVACAO':
            mensagem += (
                f"`{r['ativo']}` | {r['estrategia']}\n"
            )
    return mensagem

# Variável global para guardar os dados do Bitcoin
btc_data_cache = None

def get_btc_data():
    """Busca e armazena em cache os dados do Bitcoin."""
    global btc_data_cache
    if btc_data_cache is None:
        print("INFO: Buscando dados do Bitcoin...")
        btc_data_cache = yf.Ticker("BTC-USD").history(period="1y", progress=False)
        if not btc_data_cache.empty:
            btc_data_cache['MME21'] = ta.ema(btc_data_cache['Close'], length=21)
    return btc_data_cache

def buscar_gatilho_horario(ticker, data_sinal, tipo_setup):
    """Busca o gatilho de confirmação no gráfico de 1 hora."""
    try:
        dados_h1 = yf.Ticker(ticker).history(period="5d", interval="1h", progress=False)
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
        dados_d1 = yf.Ticker(ticker).history(period="1y", progress=False)
        if dados_d1.empty or len(dados_d1) < 201: return None

        # --- Cálculo de Indicadores no Diário ---
        dados_d1['MME200'] = ta.ema(dados_d1['Close'], length=200)
        dados_d1['Volume_MA20'] = dados_d1['Volume'].rolling(window=20).mean()
        dados_d1['RSI'] = ta.rsi(dados_d1['Close'], length=14)
        dados_d1['ATR'] = ta.atr(dados_d1['High'], dados_d1['Low'], dados_d1['Close'], length=14)
        bbands = ta.bbands(dados_d1['Close'], length=20, std=2)
        if bbands is not None and not bbands.empty:
            dados_d1['BB_Width'] = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
            dados_d1['BB_Width_MA20'] = dados_d1['BB_Width'].rolling(window=20).mean()
        else:
            dados_d1['BB_Width'], dados_d1['BB_Width_MA20'] = 0, 0
        
        indices_pivos_fundo, _ = find_peaks(-dados_d1['Low'], distance=10); dados_d1['pivo_fundo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_fundo], 'pivo_fundo'] = dados_d1['Low']
        indices_pivos_topo, _ = find_peaks(dados_d1['High'], distance=10); dados_d1['pivo_topo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_topo], 'pivo_topo'] = dados_d1['High']
        indices_pivos_rsi_fundo, _ = find_peaks(-dados_d1['RSI'], distance=10); dados_d1['pivo_rsi_fundo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_rsi_fundo], 'pivo_rsi_fundo'] = dados_d1['RSI']
        indices_pivos_rsi_topo, _ = find_peaks(dados_d1['RSI'], distance=10); dados_d1['pivo_rsi_topo'] = np.nan; dados_d1.loc[dados_d1.index[indices_pivos_rsi_topo], 'pivo_rsi_topo'] = dados_d1['RSI']
        vela_ob_bullish = (dados_d1['Open'].shift(1) > dados_d1['Close'].shift(1)); movimento_forte_bullish = (dados_d1['Close'] > dados_d1['High'].shift(1)); dados_d1['Bullish_OB'] = vela_ob_bullish & movimento_forte_bullish
        vela_ob_bearish = (dados_d1['Open'].shift(1) < dados_d1['Close'].shift(1)); movimento_forte_bearish = (dados_d1['Close'] < dados_d1['Low'].shift(1)); dados_d1['Bearish_OB'] = vela_ob_bearish & movimento_forte_bearish
        dados_d1['range_low_30d'] = dados_d1['Low'].rolling(window=30).min()
        dados_d1['divergencia_bullish_ativa'] = False; dados_d1['divergencia_bearish_ativa'] = False
        
        # --- Lógica de Divergências ---
        pivos_fundo_validos = dados_d1.dropna(subset=['pivo_fundo']); pivos_rsi_fundo_validos = dados_d1.dropna(subset=['pivo_rsi_fundo'])
        for i in range(1, len(pivos_fundo_validos)):
            preco_pivo_atual = pivos_fundo_validos['pivo_fundo'].iloc[i]; preco_pivo_anterior = pivos_fundo_validos['pivo_fundo'].iloc[i-1]
            data_pivo_preco_atual = pivos_fundo_validos.index[i]
            if preco_pivo_atual < preco_pivo_anterior:
                rsi_pivo_anterior_proximo = pivos_rsi_fundo_validos[pivos_rsi_fundo_validos.index < data_pivo_preco_atual].tail(1)
                if not rsi_pivo_anterior_proximo.empty:
                    rsi_pivo_anterior = rsi_pivo_anterior_proximo['pivo_rsi_fundo'].iloc[0]
                    rsi_pivo_atual_proximo = pivos_rsi_fundo_validos[pivos_rsi_fundo_validos.index >= data_pivo_preco_atual].head(1)
                    if not rsi_pivo_atual_proximo.empty:
                        rsi_pivo_atual = rsi_pivo_atual_proximo['pivo_rsi_fundo'].iloc[0]
                        if rsi_pivo_atual > rsi_pivo_anterior:
                            indice_inicio = dados_d1.index.get_loc(data_pivo_preco_atual)
                            dados_d1.iloc[indice_inicio:indice_inicio+10, dados_d1.columns.get_loc('divergencia_bullish_ativa')] = True
        
        pivos_topo_validos = dados_d1.dropna(subset=['pivo_topo']); pivos_rsi_topo_validos = dados_d1.dropna(subset=['pivo_rsi_topo'])
        for i in range(1, len(pivos_topo_validos)):
            preco_pivo_atual = pivos_topo_validos['pivo_topo'].iloc[i]; preco_pivo_anterior = pivos_topo_validos['pivo_topo'].iloc[i-1]
            data_pivo_preco_atual = pivos_topo_validos.index[i]
            if preco_pivo_atual > preco_pivo_anterior:
                rsi_pivo_anterior_proximo = pivos_rsi_topo_validos[pivos_rsi_topo_validos.index < data_pivo_preco_atual].tail(1)
                if not rsi_pivo_anterior_proximo.empty:
                    rsi_pivo_anterior = rsi_pivo_anterior_proximo['pivo_rsi_topo'].iloc[0]
                    rsi_pivo_atual_proximo = pivos_rsi_topo_validos[pivos_rsi_topo_validos.index >= data_pivo_preco_atual].head(1)
                    if not rsi_pivo_atual_proximo.empty:
                        rsi_pivo_atual = rsi_pivo_atual_proximo['pivo_rsi_topo'].iloc[0]
                        if rsi_pivo_atual < rsi_pivo_anterior:
                            indice_inicio = dados_d1.index.get_loc(data_pivo_preco_atual)
                            dados_d1.iloc[indice_inicio:indice_inicio+10, dados_d1.columns.get_loc('divergencia_bearish_ativa')] = True

        # --- Verificação de Setups no Penúltimo Dia ---
        penultimo_dia = dados_d1.iloc[-2]; antepenultimo_dia = dados_d1.iloc[-3]; ultimo_dia = dados_d1.iloc[-1]
        setups_encontrados = []
        score_compra = 0; score_venda = 0
        
        # --- FILTROS GERAIS ---
        regime_nao_explosivo = penultimo_dia['BB_Width'] < penultimo_dia['BB_Width_MA20']
        tendencia_de_alta = penultimo_dia['Close'] > penultimo_dia['MME200']
        tendencia_de_baixa = penultimo_dia['Close'] < penultimo_dia['MME200']
        btc_em_alta = True
        if ticker != "BTC-USD":
            btc_data = get_btc_data()
            if btc_data is None or btc_data.empty: return None
            btc_no_dia = btc_data.loc[btc_data.index.asof(penultimo_dia.name)]
            btc_em_alta = btc_no_dia['Close'] > btc_no_dia['MME21'] if pd.notna(btc_no_dia['Close']) else False

        # --- PROCURA POR SETUPS DE COMPRA ---
        if tendencia_de_alta and btc_em_alta and regime_nao_explosivo:
            # Setup 1: Wyckoff Spring com Volume
            suporte_range = antepenultimo_dia['range_low_30d']
            if antepenultimo_dia['Low'] < suporte_range and penultimo_dia['Close'] > suporte_range and penultimo_dia['Volume'] > penultimo_dia['Volume_MA20']:
                score_compra += 1
                setups_encontrados.append({'tipo': 'COMPRA_SPRING', 'stop_base': antepenultimo_dia['Low'], 'atr': penultimo_dia['ATR']})
            # Setup 2: OB + Divergência de Alta
            ob_recente = dados_d1.loc[:antepenultimo_dia.name][dados_d1['Bullish_OB']].tail(1)
            if not ob_recente.empty:
                ob_index = ob_recente.index[0]; ob_real_index = dados_d1.index[dados_d1.index.get_loc(ob_index)-1]
                ob_low = dados_d1.loc[ob_real_index, 'Low']; ob_high = dados_d1.loc[ob_real_index, 'High']
                preco_testou_ob = (penultimo_dia['Low'] <= ob_high and penultimo_dia['Low'] >= ob_low)
                if preco_testou_ob and penultimo_dia['divergencia_bullish_ativa']:
                     score_compra += 1
                     setups_encontrados.append({'tipo': 'COMPRA_DIVERGENCE', 'stop_base': ob_low, 'atr': penultimo_dia['ATR']})
        
        # --- PROCURA POR SETUPS DE VENDA ---
        if tendencia_de_baixa and regime_nao_explosivo:
            # Setup 3: Captura de Liquidez com Volume
            pivo_topo_recente = dados_d1.loc[:antepenultimo_dia.name].dropna(subset=['pivo_topo']).tail(1)
            if not pivo_topo_recente.empty:
                pivo_topo_valor = pivo_topo_recente['pivo_topo'].iloc[0]
                if antepenultimo_dia['High'] > pivo_topo_valor and penultimo_dia['Close'] < pivo_topo_valor and penultimo_dia['Volume'] > penultimo_dia['Volume_MA20']:
                    score_venda += 1
                    setups_encontrados.append({'tipo': 'VENDA_LIQUIDITY', 'stop_base': antepenultimo_dia['High'], 'atr': penultimo_dia['ATR']})
            # Setup 4: OB + Divergência de Baixa
            ob_recente_baixa = dados_d1.loc[:antepenultimo_dia.name][dados_d1['Bearish_OB']].tail(1)
            if not ob_recente_baixa.empty:
                ob_index = ob_recente_baixa.index[0]; ob_real_index = dados_d1.index[dados_d1.index.get_loc(ob_index)-1]
                ob_low = dados_d1.loc[ob_real_index, 'Low']; ob_high = dados_d1.loc[ob_real_index, 'High']
                preco_testou_ob = (penultimo_dia['High'] >= ob_low and penultimo_dia['High'] <= ob_high)
                if preco_testou_ob and penultimo_dia['divergencia_bearish_ativa']:
                    score_venda += 1
                    setups_encontrados.append({'tipo': 'VENDA_DIVERGENCE', 'stop_base': ob_high, 'atr': penultimo_dia['ATR']})

        if not setups_encontrados: return None
        
        # --- Lógica de Classificação ---
        score_total = score_compra + score_venda
        setup_principal = setups_encontrados[0]
        stop_dinamico = setup_principal['stop_base'] - (setup_principal['atr'] * 0.5) if 'COMPRA' in setup_principal['tipo'] else setup_principal['stop_base'] + (setup_principal['atr'] * 0.5)

        base_result = {
            'ativo': ticker,
            'estrategia': setup_principal['tipo'],
            'score': score_total,
            'data_setup': penultimo_dia.name.strftime('%Y-%m-%d'),
            'stop_potencial': stop_dinamico
        }

        if score_total >= 1:
            resultado_h1 = buscar_gatilho_horario(ticker, ultimo_dia.name, setup_principal['tipo'])
            if resultado_h1 and resultado_h1['gatilho_encontrado']:
                # Status de Gatilho Encontrado, mas ainda depende do score para ser de alta prob. ou observação
                 base_result['status'] = 'GATILHO_ENCONTRADO'
            else:
                base_result['status'] = 'EM_OBSERVACAO' if score_total == 1 else 'AGUARDANDO_GATILHO'
            
            return base_result
            
    except Exception as e:
        print(f"ERRO CRÍTICO no ativo {ticker}: {e}")
        return None
    return None

async def main():
    """Função principal que executa o scanner e envia os resultados."""
    print("--- INICIANDO SCANNER DE CRIPTOMOEDAS ---")
    
    # ### ALTERAÇÃO ###
    # ETAPA 1: LISTA COM 150 ATIVOS FOCADOS NA MEXC
    watchlist = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "SHIB-USD", "DOT-USD",
        "LINK-USD", "TRX-USD", "MATIC-USD", "BCH-USD", "LTC-USD", "NEAR-USD", "UNI-USD", "XLM-USD", "ATOM-USD", "ETC-USD",
        "XMR-USD", "ICP-USD", "HBAR-USD", "VET-USD", "FIL-USD", "APT-USD", "CRO-USD", "LDO-USD", "ARB-USD", "QNT-USD",
        "AAVE-USD", "ALGO-USD", "STX-USD", "FTM-USD", "EOS-USD", "SAND-USD", "MANA-USD", "THETA-USD", "AXS-USD", "RNDR-USD",
        "XTZ-USD", "SUI-USD", "PEPE-USD", "INJ-USD", "GALA-USD", "SNX-USD", "OP-USD", "KAS-USD", "TIA-USD", "MKR-USD",
        "RUNE-USD", "WIF-USD", "JUP-USD", "SEI-USD", "EGLD-USD", "FET-USD", "FLR-USD", "BONK-USD", "BGB-USD", "BEAM-USD",
        "DYDX-USD", "AGIX-USD", "NEO-USD", "WLD-USD", "ROSE-USD", "PYTH-USD", "GNO-USD", "CHZ-USD", "MINA-USD", "FLOW-USD",
        "KCS-USD", "FXS-USD", "KLAY-USD", "GMX-USD", "RON-USD", "CFX-USD", "CVX-USD", "ZEC-USD", "AIOZ-USD", "WEMIX-USD",
        "ENA-USD", "TWT-USD", "CAKE-USD", "CRV-USD", "FLOKI-USD", "BTT-USD", "1INCH-USD", "GMT-USD", "ZIL-USD", "ANKR-USD",
        "JASMY-USD", "KSM-USD", "LUNC-USD", "USTC-USD", "CELO-USD", "IOTA-USD", "HNT-USD", "RPL-USD", "FTT-USD", "XDC-USD",
        "PAXG-USD", "DASH-USD", "ENS-USD", "BAT-USD", "ZRX-USD", "YFI-USD", "SUSHI-USD", "UMA-USD", "REN-USD", "KNC-USD",
        "BAL-USD", "LRC-USD", "OCEAN-USD", "POWR-USD", "RLC-USD", "BAND-USD", "TRB-USD", "API3-USD", "BLZ-USD", "PERP-USD",
        "COTI-USD", "STORJ-USD", "SKL-USD", "CTSI-USD", "NKN-USD", "OGN-USD", "NMR-USD", "IOTX-USD", "AUDIO-USD", "CVC-USD",
        "LOOM-USD", "MDT-USD", "REQ-USD", "RLY-USD", "TRU-USD", "ACH-USD", "AGLD-USD", "ALCX-USD", "AMP-USD", "ARPA-USD",
        "AUCTION-USD", "BADGER-USD", "BICO-USD", "BNT-USD", "BOND-USD", "CLV-USD", "CTX-USD", "DDX-USD", "DIA-USD", "DREP-USD"
    ]
    
    print(f"Watchlist definida com {len(watchlist)} ativos.")

    # ETAPA 2: EXECUÇÃO DO SCANNER
    setups_aguardando = []
    setups_observacao = []

    get_btc_data()

    total_ativos = len(watchlist)
    for i, ativo in enumerate(watchlist):
        print(f"Analisando {i+1}/{total_ativos}: {ativo}...")
        resultado = analisar_ativo_mtf(ativo)
        if resultado:
            if resultado.get('status') == 'AGUARDANDO_GATILHO':
                setups_aguardando.append(resultado)
            elif resultado.get('status') == 'EM_OBSERVACAO':
                setups_observacao.append(resultado)

    # ETAPA 3: ENVIO DO RELATÓRIO
    print("\n--- Compilando e enviando relatório ---")
    
    msg_aguardando = formatar_mensagem(setups_aguardando, "🚨 SETUPS DE ALTA PROBABILIDADE (SCORE ≥ 2)")
    if msg_aguardando:
      await enviar_mensagem_telegram(msg_aguardando)
      await asyncio.sleep(1) 

    msg_observacao = formatar_mensagem(setups_observacao, "👀 ATIVOS EM OBSERVAÇÃO (SCORE = 1)")
    if msg_observacao:
      await enviar_mensagem_telegram(msg_observacao)
    
    print("\n--- EXECUÇÃO CONCLUÍDA ---")

if __name__ == "__main__":
    asyncio.run(main())
