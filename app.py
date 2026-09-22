import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestão de Frota - Consumo", layout="wide", page_icon="🚗")

st.title("🚗 Gestão de Frota - Relatório Semestral de Consumo e Abastecimento")
st.caption("Painel executivo com capacidade de tanques ajustada por modelo (Gol, Fiorino, etc.)")

# --- CADASTRO PRÉVIO DE PLACAS DA FROTA (OPCIONAL) ---
# Você pode cadastrar previamente as placas conhecidas aqui:
CADASTRO_FROTA = {
    # Exemplo:
    # "ABC1D23": "Gol",
    # "XYZ9K88": "Fiorino",
}

CAPACIDADES_POR_MODELO = {
    "Gol": 55.0,
    "Fiorino": 58.0,
    "Outro / Padrão": 50.0
}

# Sidebar - Upload dos relatórios
st.sidebar.header("📁 Importar Relatórios")
uploaded_files = st.sidebar.file_uploader(
    "Selecione os arquivos mensais do RotaExata (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

def parse_rotaexata(file):
    df_raw = pd.read_excel(file, sheet_name=0)
    df_data = df_raw.iloc[4:].copy()
    df_data.columns = df_raw.iloc[3].values
    
    df_clean = df_data[df_data['Data'].notna() & (df_data['Data'] != 'TOTALIZADOR')].copy()
    
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
    
    # --- CONFIGURAÇÃO DE CAPACIDADE DE TANQUE POR PLACA ---
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Capacidade dos Tanques")
    
    placas_unicas = sorted(df['Placa'].dropna().unique())
    
    # Monta tabela inicial de configuração de tanques
    config_data = []
    for placa in placas_unicas:
        modelo_detectado = CADASTRO_FROTA.get(placa, "Outro / Padrão")
        cap_padrao = CAPACIDADES_POR_MODELO.get(modelo_detectado, 50.0)
        config_data.append({"Placa": placa, "Modelo": modelo_detectado, "Capacidade Tanque (L)": cap_padrao})
        
    df_config_tanques = pd.DataFrame(config_data)
    
    with st.sidebar.expander("🛠️ Ajustar Tanques das Placas", expanded=True):
        st.write("Ajuste a capacidade real dos tanques conforme a frota:")
        df_edited = st.data_editor(
            df_config_tanques,
            column_config={
                "Modelo": st.column_config.SelectboxColumn(
                    "Modelo Veículo",
                    options=["Gol", "Fiorino", "Outro / Padrão"],
                    required=True
                ),
                "Capacidade Tanque (L)": st.column_config.NumberColumn(
                    "Capacidade (L)",
                    min_value=30.0,
                    max_value=120.0,
                    step=1.0,
                    format="%.0f L"
                )
            },
            disabled=["Placa"],
            hide_index=True,
            key="tanque_editor"
        )
    
    # Atualiza capacidades com base na edição do usuário
    # Se o modelo for alterado para Gol/Fiorino, aplica a regra
    def definir_capacidade(row):
        mod = row['Modelo']
        cap = row['Capacidade Tanque (L)']
        if mod == "Gol" and cap == 50.0:
            return 55.0
        elif mod == "Fiorino" and cap == 50.0:
            return 58.0
        return cap

    df_edited['Capacidade Real'] = df_edited.apply(definir_capacidade, axis=1)
    mapa_tanques = dict(zip(df_edited['Placa'], df_edited['Capacidade Real']))
    
    # Sobrescreve a coluna de capacidade no relatório
    df['Capacidade do tanque'] = df['Placa'].map(mapa_tanques).fillna(df['Capacidade do tanque'])

    # --- FILTROS DE VISUALIZAÇÃO ---
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filtros")
    placas_selecionadas = st.sidebar.multiselect("Filtrar por Placa", options=placas_unicas, default=placas_unicas)
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
    
    # --- GRÁFICOS ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("💰 Custo por Veículo")
        cost_by_plate = df_filtered.groupby('Placa')['Custo total'].sum().reset_index().sort_values(by='Custo total', ascending=False)
        fig_cost = px.bar(cost_by_plate, x='Placa', y='Custo total', text_auto='.2f', color='Custo total', color_continuous_scale='Reds')
        st.plotly_chart(fig_cost, use_container_width=True)
        
        st.subheader("⛽ Consumo por Tipo de Combustível")
        fuel_perf = df_filtered.groupby('Tipo de Combustível').agg({'Km rodado': 'sum', 'Litros abastecidos': 'sum'}).reset_index()
        fuel_perf['Média km/L'] = fuel_perf['Km rodado'] / fuel_perf['Litros abastecidos']
        fig_fuel = px.bar(fuel_perf, x='Tipo de Combustível', y='Média km/L', color='Tipo de Combustível', text_auto='.2f')
        st.plotly_chart(fig_fuel, use_container_width=True)

    with col_right:
        st.subheader("🏆 Média de Consumo por Placa (km/L)")
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
    st.subheader("⚠️ Painel de Auditoria de Abastecimentos Atípicos")
    
    anomalias_tanque = df_filtered[df_filtered['Litros abastecidos'] > df_filtered['Capacidade do tanque']]
    if not anomalias_tanque.empty:
        st.error(f"⚠️ Identificados {len(anomalias_tanque)} abastecimentos que superam a capacidade real ajustada do tanque!")
        st.dataframe(
            anomalias_tanque[['Data', 'Placa', 'Descrição', 'Tipo de Combustível', 'Litros abastecidos', 'Capacidade do tanque', 'Custo total']],
            column_config={
                "Capacidade do tanque": st.column_config.NumberColumn("Capacidade Real (L)", format="%.0f L"),
                "Litros abastecidos": st.column_config.NumberColumn("Abastecido (L)", format="%.2f L"),
                "Custo total": st.column_config.NumberColumn("Custo Total (R$)", format="R$ %.2f")
            }
        )
    else:
        st.success("✅ Nenhum abastecimento excedeu a capacidade ajustada do tanque.")

    with st.expander("📋 Ver todos os dados consolidados"):
        st.dataframe(df_filtered)

else:
    st.info("👈 Faça o upload dos relatórios mensais (.xlsx) na barra lateral para visualizar as análises.")
