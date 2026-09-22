import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Gestão de Frota - Consumo Sanitizado", layout="wide", page_icon="🚗")

st.title("🚗 Gestão de Frota - Dashboard Semestral com Tratamento Estatístico")
st.caption("Painel executivo com sanitização automática de inconsistências de digitação e cálculo de margem de erro")

# --- CONFIGURAÇÃO DE CAPACIDADES ---
CAPACIDADES_POR_MODELO = {
    "Gol": 55.0,
    "Fiorino": 58.0,
    "Outro / Padrão": 50.0
}

# Sidebar - Upload
st.sidebar.header("📁 1. Importar Relatórios")
uploaded_files = st.sidebar.file_uploader(
    "Selecione os arquivos do RotaExata (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ 2. Trava Sanitizadora de Dados")
usar_sanitizacao = st.sidebar.toggle("Ativar Filtro Refinado de Inconsistências", value=True)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 3. Capacidade dos Tanques")

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
    df_raw = pd.concat(df_list, ignore_index=True)
    
    df_raw['Km_Calculado'] = df_raw['Km final'] - df_raw['Km inicial']
    df_raw['KmL_Real_Abastecido'] = df_raw['Km_Calculado'] / df_raw['Litros abastecidos']
    df_raw['Custo_Km_Real'] = df_raw['Custo total'] / df_raw['Km_Calculado']

    # --- CONFIGURAÇÃO DE TANQUES POR PLACA ---
    placas_unicas = sorted(df_raw['Placa'].dropna().unique())
    config_data = [{"Placa": p, "Modelo": "Outro / Padrão", "Capacidade Tanque (L)": 50.0} for p in placas_unicas]
    df_config = pd.DataFrame(config_data)
    
    with st.sidebar.expander("🛠️ Definir Tanque por Placa", expanded=False):
        df_edited = st.data_editor(
            df_config,
            column_config={
                "Modelo": st.column_config.SelectboxColumn("Modelo", options=["Gol", "Fiorino", "Outro / Padrão"], required=True),
                "Capacidade Tanque (L)": st.column_config.NumberColumn("Capacidade (L)", min_value=30.0, max_value=120.0)
            },
            disabled=["Placa"],
            hide_index=True,
            key="tanque_editor"
        )
    
    def get_cap(row):
        mod = row['Modelo']
        cap = row['Capacidade Tanque (L)']
        if mod == "Gol" and cap == 50.0: return 55.0
        if mod == "Fiorino" and cap == 50.0: return 58.0
        return cap

    df_edited['Capacidade_Ajustada'] = df_edited.apply(get_cap, axis=1)
    mapa_tanques = dict(zip(df_edited['Placa'], df_edited['Capacidade_Ajustada']))
    df_raw['Capacidade_Tanque_Real'] = df_raw['Placa'].map(mapa_tanques).fillna(50.0)

    # --- REGRAS DE SANITIZAÇÃO ---
    def diagnosticar_registro(row):
        motivos = []
        if pd.isna(row['Km_Calculado']) or row['Km_Calculado'] <= 0:
            motivos.append("Odômetro Invalido/Negativo")
        elif row['Km_Calculado'] > 1200:
            motivos.append("Km Excessivo p/ Abastecimento (>1200km)")
            
        if pd.isna(row['Custo por litro']) or not (4.0 <= row['Custo por litro'] <= 9.0):
            motivos.append("Preço/Litro Atípico (<R$4 ou >R$9)")
            
        if row['Litros abastecidos'] > (row['Capacidade_Tanque_Real'] * 1.10):
            motivos.append(f"Volume Excede Tanque ({row['Litros abastecidos']}L > {row['Capacidade_Tanque_Real']}L)")
            
        kml = row['KmL_Real_Abastecido']
        if pd.isna(kml) or not (3.0 <= kml <= 22.0):
            motivos.append(f"Média Impossível ({kml:.1f} km/L)")
            
        return " | ".join(motivos) if motivos else "VÁLIDO"

    df_raw['Status_Auditoria'] = df_raw.apply(diagnosticar_registro, axis=1)
    df_validos = df_raw[df_raw['Status_Auditoria'] == "VÁLIDO"].copy()
    df_invalidos = df_raw[df_raw['Status_Auditoria'] != "VÁLIDO"].copy()

    df_work = df_validos if usar_sanitizacao else df_raw.copy()

    # --- INDICADORES EXECUTIVOS ---
    st.subheader("📌 Indicadores Consolidados da Frota")
    
    n_amostras = len(df_work)
    custo_total = df_work['Custo total'].sum()
    km_total = df_work['Km_Calculado'].sum()
    litros_totais = df_work['Litros abastecidos'].sum()
    
    media_kml = df_work['KmL_Real_Abastecido'].mean()
    std_kml = df_work['KmL_Real_Abastecido'].std()
    margem_erro_kml = 1.96 * (std_kml / np.sqrt(n_amostras)) if n_amostras > 0 else 0
    
    media_custo_km = custo_total / km_total if km_total > 0 else 0
    std_custo_km = df_work['Custo_Km_Real'].std()
    margem_erro_custo_km = 1.96 * (std_custo_km / np.sqrt(n_amostras)) if n_amostras > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Investimento Total", f"R$ {custo_total:,.2f}")
    k2.metric("Km Total Rodado", f"{km_total:,.0f} km")
    k3.metric("Volume Abastecido", f"{litros_totais:,.1f} L")
    k4.metric("Consumo Médio Real", f"{media_kml:.2f} km/L", delta=f"± {margem_erro_kml:.2f} km/L (Margem)", delta_color="normal")
    k5.metric("Custo Médio / Km", f"R$ {media_custo_km:.2f}", delta=f"± R$ {margem_erro_custo_km:.2f} / km", delta_color="normal")

    st.markdown("---")
    c_est1, c_est2, c_est3 = st.columns([1, 1, 1])
    
    with c_est1:
        st.info(f"📊 **Variabilidade de Consumo (Desvio Padrão):**\n"
                f"* **Desvio Padrão ($\sigma$):** `{std_kml:.2f} km/L`\n"
                f"* **Intervalo Estimado (95% CI):** `[{media_kml - margem_erro_kml:.2f} a {media_kml + margem_erro_kml:.2f}] km/L`")
    with c_est2:
        st.info(f"💵 **Variabilidade de Custo por Km:**\n"
                f"* **Desvio Padrão ($\sigma$):** `R$ {std_custo_km:.2f} / km`\n"
                f"* **Intervalo Estimado (95% CI):** `[R$ {max(0, media_custo_km - margem_erro_custo_km):.2f} a R$ {media_custo_km + margem_erro_custo_km:.2f}] / km`")
    with c_est3:
        if usar_sanitizacao:
            st.success(f"🎯 **Status da Higienização:**\n"
                       f"* **Registros Válidos:** `{len(df_validos)}` ({len(df_validos)/len(df_raw)*100:.1f}%)\n"
                       f"* **Inconsistências Excluídas:** `{len(df_invalidos)}` ({len(df_invalidos)/len(df_raw)*100:.1f}%)")
        else:
            st.warning("⚠️ **Modo Dados Brutos Ativo:** Exibindo registros sem tratamento.")

    st.markdown("---")

    # --- GRÁFICOS ---
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("💰 Custo Total por Veículo (Placa)")
        cost_p = df_work.groupby('Placa')['Custo total'].sum().reset_index().sort_values(by='Custo total', ascending=False)
        fig_cost = px.bar(cost_p, x='Placa', y='Custo total', text_auto='.2f', color='Custo total', color_continuous_scale='Reds')
        st.plotly_chart(fig_cost, use_container_width=True)

    with col_r:
        st.subheader("🏆 Eficiência Média Sanitizada por Placa (km/L)")
        avg_p = df_work.groupby('Placa').agg({'Km_Calculado': 'sum', 'Litros abastecidos': 'sum'}).reset_index()
        avg_p['Média km/L'] = avg_p['Km_Calculado'] / avg_p['Litros abastecidos']
        avg_p = avg_p.sort_values(by='Média km/L', ascending=False)
        fig_avg = px.bar(avg_p, x='Placa', y='Média km/L', color='Média km/L', color_continuous_scale='Greens', text_auto='.2f')
        st.plotly_chart(fig_avg, use_container_width=True)

    # --- AUDITORIA DE ANOMALIAS ---
    st.markdown("---")
    st.subheader("🔍 Painel de Auditoria e Diagnóstico de Erros")
    if not df_invalidos.empty:
        st.error(f"⚠️ Foram identificados {len(df_invalidos)} lançamentos incorretos/atípicos nos relatórios:")
        st.dataframe(
            df_invalidos[['Data', 'Placa', 'Descrição', 'Litros abastecidos', 'Custo por litro', 'Custo total', 'Km_Calculado', 'KmL_Real_Abastecido', 'Status_Auditoria']],
            column_config={
                "Km_Calculado": st.column_config.NumberColumn("Km Rodado", format="%.0f km"),
                "KmL_Real_Abastecido": st.column_config.NumberColumn("Média Calculada", format="%.1f km/L"),
                "Status_Auditoria": st.column_config.TextColumn("Motivo da Invalidação")
            },
            hide_index=True,
            use_container_width=True
        )

    # --- NOVO MÓDULO: GERADOR DE RELATÓRIO EXECUTIVO ---
    st.markdown("---")
    st.subheader("📝 Gerador de Relatório Executivo para a Diretoria")
    
    if st.button("📄 Gerar Sumário Executivo do Período"):
        top_veiculo_custo = cost_p.iloc[0]['Placa'] if not cost_p.empty else "N/A"
        top_veiculo_valor = cost_p.iloc[0]['Custo total'] if not cost_p.empty else 0.0
        
        texto_relatorio = f"""========================================================================
RELATÓRIO EXECUTIVO DE AUDITORIA E DESEMPENHO DA FROTA
========================================================================

1. RESUMO DOS INDICADORES CONSOLIDADOS
------------------------------------------------------------------------
* Total de Registros Analisados: {len(df_raw)} lançamentos
* Registros Validados (Sanitizados): {len(df_validos)} ({len(df_validos)/len(df_raw)*100:.1f}%)
* Registros com Inconsistências: {len(df_invalidos)} ({len(df_invalidos)/len(df_raw)*100:.1f}%)

* Investimento Total em Combustível (Válido): R$ {custo_total:,.2f}
* Quilometragem Total Efecitivamente Rodada: {km_total:,.0f} km
* Volume Total de Combustível Consumido: {litros_totais:,.1f} Litros

2. ANÁLISE DE EFICIÊNCIA E MARGEM DE ERRO
------------------------------------------------------------------------
* Média Sanitizada de Consumo: {media_kml:.2f} km/L
* Desvio Padrão (Variabilidade): {std_kml:.2f} km/L
* Intervalo de Confiança Estatística (95%): [{media_kml - margem_erro_kml:.2f} a {media_kml + margem_erro_kml:.2f}] km/L

* Custo Médio por Quilômetro Rodado: R$ {media_custo_km:.2f} / km
* Intervalo do Custo/Km (95%): [R$ {max(0, media_custo_km - margem_erro_custo_km):.2f} a R$ {media_custo_km + margem_erro_custo_km:.2f}] / km

3. DESTAQUES DA OPERAÇÃO
------------------------------------------------------------------------
* Maior Custo Acumulado no Período: Veículo {top_veiculo_custo} (R$ {top_veiculo_valor:,.2f})
* Custo Impactado por Lançamentos Incorretos: R$ {df_invalidos['Custo total'].sum():,.2f}

4. DIAGNÓSTICO DE AUDITORIA E PLANO DE AÇÃO
------------------------------------------------------------------------
Foram detectadas {len(df_invalidos)} anomalias operacionais derivadas de:
  a) Digitação incorreta do odômetro inicial/final pelo condutor.
  b) Volume abastecido divergente da capacidade física do tanque.
  c) Lançamentos isolados com preço por litro atípico.

Recomenda-se:
  1) Orientação das equipes operacionais sobre a digitação correta do odômetro.
  2) Ajuste dos dados incorretos apontados na aba de auditoria direto no portal RotaExata.
========================================================================
"""
        st.text_area("Pré-visualização do Relatório Gerado:", value=texto_relatorio, height=350)
        
        st.download_button(
            label="💾 Baixar Relatório Executivo (.txt)",
            data=texto_relatorio,
            file_name="Relatorio_Executivo_Frota.txt",
            mime="text/plain"
        )

else:
    st.info("👈 Envie os relatórios do RotaExata na barra lateral para iniciar o processamento.")
