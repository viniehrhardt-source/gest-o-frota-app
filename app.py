import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestão de Frota - Consumo", layout="wide", page_icon="🚗")

st.title("🚗 Gestão de Frota - Relatório Semestral de Consumo e Abastecimento")
st.caption("Painel executivo para análise de indicadores do RotaExata")

# Sidebar - Upload dos relatórios
st.sidebar.header("📁 Importar Relatórios")
uploaded_files = st.sidebar.file_uploader(
    "Selecione os arquivos mensais do RotaExata (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

def parse_rotaexata(file):
    df_raw = pd.read_excel(file, sheet_name=0)
    # Identifica a linha de cabeçalhos
    df_data = df_raw.iloc[4:].copy()
    df_data.columns = df_raw.iloc[3].values
    
    # Filtra linhas válidas removendo cabeçalhos e totalizadores intermediários
    df_clean = df_data[df_data['Data'].notna() & (df_data['Data'] != 'TOTALIZADOR')].copy()
    
    # Limpeza de formatação numérica (R$, Km, L, vírgulas)
    def clean_num(val):
        if pd.isna(val): return None
        s = str(val).replace('\xa0', '').replace('R$', '').replace('Km', '').replace('L', '').replace(' ', '').strip()
        s = s.replace('.', '').replace(',', '.') if ',' in s else s
        try:
            return float(s)
        except:
            return None
            
    num_cols = ['Km inicial', 'Km final', 'Km rodado', 'Litros abastecidos', 
                'Litros consumidos', 'Capacidade do tanque', 'Custo por litro', 
                'Custo total', 'Média km/litro', 'Média custo/km']
    
    for col in num_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(clean_num)
            
    df_clean['Data'] = pd.to_datetime(df_clean['Data'], format='%d/%m/%Y', errors='coerce')
    return df_clean

if uploaded_files:
    df_list = [parse_rotaexata(f) for f in uploaded_files]
    df = pd.concat(df_list, ignore_index=True)
    
    # --- FILTROS ---
    st.sidebar.header("🔍 Filtros de Visualização")
    placas_selecionadas = st.sidebar.multiselect("Filtrar por Placa", options=sorted(df['Placa'].dropna().unique()), default=sorted(df['Placa'].dropna().unique()))
    combustivel_selecionado = st.sidebar.multiselect("Tipo de Combustível", options=sorted(df['Tipo de Combustível'].dropna().unique()), default=sorted(df['Tipo de Combustível'].dropna().unique()))
    
    df_filtered = df[(df['Placa'].isin(placas_selecionadas)) & (df['Tipo de Combustível'].isin(combustivel_selecionado))]
    
    # --- KPIS PRINCIPAIS ---
    st.subheader("📌 Visão Geral do Período")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    custo_total = df_filtered['Custo total'].sum()
    km_total = df_filtered['Km rodado'].sum()
    litros_totais = df_filtered['Litros abastecidos'].sum()
    media_km_l = km_total / litros_totais if litros_totais > 0 else 0
    custo_medio_km = custo_total / km_total if km_total > 0 else 0
    
    kpi1.metric("Investimento Total", f"R$ {custo_total:,.2f}")
    kpi2.metric("Km Rodados", f"{km_total:,.0f} km")
    kpi3.metric("Volume Abastecido", f"{litros_totais:,.1f} L")
    kpi4.metric("Consumo Médio", f"{media_km_l:.2f} km/L")
    kpi5.metric("Custo Médio / Km", f"R$ {custo_medio_km:.2f}")
    
    st.markdown("---")
    
    # --- GRÁFICOS E TABELAS ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("💰 Custo por Veículo (Top Custos)")
        cost_by_plate = df_filtered.groupby('Placa')['Custo total'].sum().reset_index().sort_values(by='Custo total', ascending=False)
        fig_cost = px.bar(cost_by_plate, x='Placa', y='Custo total', text_auto='.2f', color='Custo total', color_continuous_scale='Reds')
        st.plotly_chart(fig_cost, use_container_width=True)
        
        st.subheader("⛽ Consumo por Tipo de Combustível")
        fuel_perf = df_filtered.groupby('Tipo de Combustível').agg({'Km rodado': 'sum', 'Litros abastecidos': 'sum', 'Custo total': 'sum'}).reset_index()
        fuel_perf['Média km/L'] = fuel_perf['Km rodado'] / fuel_perf['Litros abastecidos']
        fig_fuel = px.bar(fuel_perf, x='Tipo de Combustível', y='Média km/L', color='Tipo de Combustível', text_auto='.2f')
        st.plotly_chart(fig_fuel, use_container_width=True)

    with col_right:
        st.subheader("🏆 Melhores vs. Piores Médias (km/L)")
        avg_km_l = df_filtered.groupby('Placa').agg({'Km rodado': 'sum', 'Litros abastecidos': 'sum'}).reset_index()
        avg_km_l['Média km/L'] = avg_km_l['Km rodado'] / avg_km_l['Litros abastecidos']
        avg_km_l = avg_km_l.sort_values(by='Média km/L', ascending=False)
        fig_avg = px.bar(avg_km_l, x='Placa', y='Média km/L', color='Média km/L', color_continuous_scale='Greens', text_auto='.2f')
        st.plotly_chart(fig_avg, use_container_width=True)
        
        st.subheader("👤 Custos por Condutor/Responsável")
        driver_cost = df_filtered.groupby('Descrição')['Custo total'].sum().reset_index().sort_values(by='Custo total', ascending=False)
        fig_driver = px.pie(driver_cost, names='Descrição', values='Custo total', hole=0.4)
        st.plotly_chart(fig_driver, use_container_width=True)

    # --- AUDITORIA DE ANOMALIAS ---
    st.markdown("---")
    st.subheader("⚠️ Painel de Auditoria e Inconsistências")
    
    anomalias_tanque = df_filtered[df_filtered['Litros abastecidos'] > df_filtered['Capacidade do tanque']]
    if not anomalias_tanque.empty:
        st.error(f"⚠️ Foram identificados {len(anomalias_tanque)} registros onde o volume abastecido excede a capacidade do tanque!")
        st.dataframe(anomalias_tanque[['Data', 'Placa', 'Descrição', 'Tipo de Combustível', 'Litros abastecidos', 'Capacidade do tanque', 'Custo total']])
    else:
        st.success("✅ Nenhuma anomalia de capacidade de tanque detectada.")

    with st.expander("📋 Ver todos os dados consolidados"):
        st.dataframe(df_filtered)

else:
    st.info("👈 Por favor, faça o upload de um ou mais relatórios `.xlsx` na barra lateral esquerda para iniciar a análise.")
