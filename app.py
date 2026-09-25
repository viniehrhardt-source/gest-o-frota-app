import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import re
import pypdf

st.set_page_config(page_title="Gestão de Frota - RotaExata", layout="wide", page_icon="🚗")

# --- SELEÇÃO DE MÓDULO ---
st.sidebar.title("🎛️ Módulos de Análise")
modulo = st.sidebar.radio(
    "Selecione o relatório:",
    ["⏱️ Veículo Parado e Ligado (PDF/Excel)", "⛽ Abastecimentos e Custos (Excel)"]
)

# ==============================================================================
# MÓDULO 1: VEÍCULO PARADO E LIGADO
# ==============================================================================
if modulo == "⏱️ Veículo Parado e Ligado (PDF/Excel)":
    st.title("⏱️ Análise de Veículos Parados com Motor Ligado (Idling)")
    st.caption("Diagnóstico completo: desperdício financeiro, ranking de infratores, evolução temporal e análise de horários")

    st.sidebar.markdown("---")
    st.sidebar.header("📁 Importar Relatórios")
    uploaded_files_parado = st.sidebar.file_uploader(
        "Selecione os arquivos de Paradas (.pdf ou .xlsx)", 
        type=["pdf", "xlsx"], 
        accept_multiple_files=True
    )

    # Parâmetros de Custo de Idling
    st.sidebar.markdown("---")
    st.sidebar.header("💸 Parâmetros de Desperdício")
    preco_litro = st.sidebar.number_input("Preço Médio do Combustível (R$/L)", value=6.60, step=0.10, format="%.2f")
    consumo_lh = st.sidebar.number_input("Consumo Parado em Marcha Lenta (L/h)", value=1.20, step=0.10, format="%.2f")
    
    st.sidebar.markdown("---")
    limite_minutos = st.sidebar.slider("Limiar para Alerta de Parada Crítica (min)", min_value=5, max_value=60, value=15, step=5)

    def parse_pdf_parado(file):
        reader = pypdf.PdfReader(file)
        lines = []
        for page in reader.pages:
            lines.extend(page.extract_text().split('\n'))
            
        record_pattern = re.compile(
            r'^(?P<placa>[A-Z0-9]{7}|[A-Z]{3}-\d{4})\s+'
            r'(?P<veiculo>.+?)\s+'
            r'(?P<data>\d{2}/\d{2}/\d{4})\s+'
            r'(?P<inicio>\d{2}:\d{2}:\d{2})\s+'
            r'(?P<final>\d{2}:\d{2}:\d{2})\s+'
            r'(?P<tempo_parado>\d{2,3}:\d{2}:\d{2})\s+'
            r'(?P<situacao>Parado ligado|Parado desligado)\s+'
            r'(?P<motorista_start>.+)$'
        )
        
        records = []
        current_record = None
        
        for line in lines:
            line_s = line.strip()
            match = record_pattern.match(line_s)
            if match:
                if current_record: records.append(current_record)
                m_dict = match.groupdict()
                current_record = {
                    'Placa': m_dict['placa'],
                    'Veiculo': m_dict['veiculo'],
                    'Data': m_dict['data'],
                    'Inicio': m_dict['inicio'],
                    'Final': m_dict['final'],
                    'Tempo_Parado': m_dict['tempo_parado'],
                    'Situacao': m_dict['situacao'],
                    'Motorista': m_dict['motorista_start'],
                    'Endereco': ''
                }
            elif current_record:
                if any(k in line_s for k in ['Placa Veículo', 'Total de registros', 'Página', 'Gerado em', 'Registros', 'Tempo parado total']):
                    continue
                if line_s.startswith(('Destino', '1-POSTO', 'POSTO', 'Rua', 'Quadra', 'DF-', 'Smpw', 'SHCGN', 'CLN', 'SQN')) or current_record['Endereco']:
                    current_record['Endereco'] = (current_record['Endereco'] + ' ' + line_s).strip()
                else:
                    current_record['Motorista'] = (current_record['Motorista'] + ' ' + line_s).strip()

        if current_record: records.append(current_record)

        for r in records:
            if 'Destino' in r['Motorista']:
                parts = r['Motorista'].split('Destino', 1)
                r['Motorista'] = parts[0].strip()
                r['Endereco'] = ('Destino' + parts[1] + ' ' + r['Endereco']).strip()

        return pd.DataFrame(records)

    def parse_excel_parado(file):
        df_raw = pd.read_excel(file)
        header_idx = None
        for idx, row in df_raw.iterrows():
            row_str = " ".join(row.astype(str).values)
            if "Placa" in row_str and ("Tempo parado" in row_str or "Situação" in row_str):
                header_idx = idx
                break
        if header_idx is not None:
            df_data = df_raw.iloc[header_idx + 1:].copy()
            df_data.columns = df_raw.iloc[header_idx].values
        else:
            df_data = df_raw.copy()
        df_data.columns = [str(c).strip() for c in df_data.columns]
        col_map = {'Veículo': 'Veiculo', 'Início': 'Inicio', 'Tempo parado': 'Tempo_Parado', 'Situação': 'Situacao', 'Cliente/Endereço': 'Endereco'}
        return df_data.rename(columns=col_map)

    if uploaded_files_parado:
        df_parado_list = []
        for f in uploaded_files_parado:
            if f.name.endswith('.pdf'):
                df_parado_list.append(parse_pdf_parado(f))
            else:
                df_parado_list.append(parse_excel_parado(f))
                
        df_parado = pd.concat(df_parado_list, ignore_index=True)
        
        def hms_to_sec(t):
            p = str(t).strip().split(':')
            if len(p) == 3:
                try: return int(p[0])*3600 + int(p[1])*60 + int(p[2])
                except: return 0
            return 0
            
        df_parado['Segundos_Parado'] = df_parado['Tempo_Parado'].apply(hms_to_sec)
        df_parado['Minutos_Parado'] = df_parado['Segundos_Parado'] / 60.0
        df_parado['Horas_Parado'] = df_parado['Segundos_Parado'] / 3600.0
        df_parado['Litros_Desperdiçados'] = df_parado['Horas_Parado'] * consumo_lh
        df_parado['Custo_Desperdicio'] = df_parado['Litros_Desperdiçados'] * preco_litro
        
        df_parado['Data_DT'] = pd.to_datetime(df_parado['Data'], format='%d/%m/%Y', errors='coerce')
        df_parado['Mes_Ano'] = df_parado['Data_DT'].dt.strftime('%Y-%m (%b)')
        df_parado['Hora_Inicio'] = pd.to_datetime(df_parado['Inicio'], format='%H:%M:%S', errors='coerce').dt.hour

        # --- FILTROS ---
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros de Visualização")
        motoristas_unicos = sorted(df_parado['Motorista'].dropna().unique())
        sel_motoristas = st.sidebar.multiselect("Filtrar por Motorista", options=motoristas_unicos, default=motoristas_unicos)
        
        meses_unicos = sorted(df_parado['Mes_Ano'].dropna().unique())
        sel_meses = st.sidebar.multiselect("Filtrar por Mês/Ano", options=meses_unicos, default=meses_unicos)

        df_p_filt = df_parado[(df_parado['Motorista'].isin(sel_motoristas)) & (df_parado['Mes_Ano'].isin(sel_meses))].copy()

        # --- KPIS ---
        st.subheader("📌 Indicadores Globais do Período")
        k1, k2, k3, k4, k5 = st.columns(5)
        
        tot_ocorrencias = len(df_p_filt)
        tot_horas = df_p_filt['Horas_Parado'].sum()
        tot_litros = df_p_filt['Litros_Desperdiçados'].sum()
        tot_custo = df_p_filt['Custo_Desperdicio'].sum()
        
        df_limiar = df_p_filt[df_p_filt['Minutos_Parado'] >= limite_minutos]
        tot_limiar = len(df_limiar)
        perc_limiar = (tot_limiar / tot_ocorrencias * 100) if tot_ocorrencias > 0 else 0

        k1.metric("Ocorrências Totais", f"{tot_ocorrencias} paradas")
        k2.metric(f"Paradas ≥ {limite_minutos} min", f"{tot_limiar} ({perc_limiar:.0f}%)")
        k3.metric("Tempo Total Parado", f"{int(tot_horas)}h {int((tot_horas%1)*60)}min")
        k4.metric("Combustível Perdido", f"{tot_litros:,.1f} L")
        k5.metric("Prejuízo Estimado", f"R$ {tot_custo:,.2f}")

        st.markdown("---")

        # --- QUADRO: REINCIDÊNCIA DE PARADAS CRÍTICAS (>= LIMIAR) POR MOTORISTA ---
        st.subheader(f"🚨 Quadro de Paradas Críticas (≥ {limite_minutos} minutos) por Motorista")
        
        q_agg = df_limiar.groupby('Motorista').agg(
            Qtd_Paradas_Criticas=('Placa', 'count'),
            Horas_Acumuladas=('Horas_Parado', 'sum'),
            Combustivel_Perdido_L=('Litros_Desperdiçados', 'sum'),
            Custo_Prejuizo_RS=('Custo_Desperdicio', 'sum')
        ).reset_index().sort_values(by='Qtd_Paradas_Criticas', ascending=False)
        
        c_q1, c_q2 = st.columns([1.2, 1])
        with c_q1:
            st.dataframe(
                q_agg,
                column_config={
                    "Motorista": st.column_config.TextColumn("Motorista / Condutor"),
                    "Qtd_Paradas_Criticas": st.column_config.NumberColumn(f"Paradas ≥ {limite_minutos} min", format="%d"),
                    "Horas_Acumuladas": st.column_config.NumberColumn("Tempo Total (Horas)", format="%.1f h"),
                    "Combustivel_Perdido_L": st.column_config.NumberColumn("Desperdício (L)", format="%.1f L"),
                    "Custo_Prejuizo_RS": st.column_config.NumberColumn("Prejuízo (R$)", format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
            
        with c_q2:
            fig_q = px.bar(
                q_agg.head(10), 
                x='Motorista', 
                y='Qtd_Paradas_Criticas', 
                text_auto=True,
                title=f"Top 10 Motoristas com mais Paradas ≥ {limite_minutos} min",
                color='Custo_Prejuizo_RS',
                color_continuous_scale='Reds',
                labels={'Qtd_Paradas_Criticas': 'Nº de Paradas', 'Custo_Prejuizo_RS': 'Prejuízo (R$)'}
            )
            st.plotly_chart(fig_q, use_container_width=True)

        st.markdown("---")

        # --- SEÇÃO DEDICADA: EVOLUÇÃO TEMPORAL MÊS A MÊS ---
        st.subheader("📈 Evolução Temporal e Análise do Hábito de Marcha Lenta")
        
        tab_evol1, tab_evol2, tab_evol3 = st.tabs(["📊 Evolução Mensal da Frota", "👤 Evolução Comparativa por Motorista", "📋 Matriz de Reincidência (Motorista x Mês)"])
        
        with tab_evol1:
            st.markdown("##### Tendência Geral do Desperdício da Frota ao Longo do Tempo")
            df_mes_agg = df_p_filt.groupby('Mes_Ano').agg({'Horas_Parado': 'sum', 'Custo_Desperdicio': 'sum', 'Placa': 'count'}).reset_index()
            fig_mes_line = px.line(df_mes_agg, x='Mes_Ano', y='Horas_Parado', markers=True, text='Horas_Parado',
                                   labels={'Mes_Ano': 'Mês/Ano', 'Horas_Parado': 'Horas Parado e Ligado'},
                                   title="Evolução do Total de Horas em Marcha Lenta por Mês")
            fig_mes_line.update_traces(texttemplate='%{text:.1f}h', textposition='top center')
            st.plotly_chart(fig_mes_line, use_container_width=True)

        with tab_evol2:
            st.markdown("##### Acompanhamento Individual do Hábito dos Motoristas")
            top_drivers = df_p_filt.groupby('Motorista')['Horas_Parado'].sum().nlargest(5).index.tolist()
            sel_drivers_chart = st.multiselect("Selecione os motoristas para comparar a evolução:", options=motoristas_unicos, default=top_drivers)
            
            df_driver_month = df_p_filt[df_p_filt['Motorista'].isin(sel_drivers_chart)].groupby(['Mes_Ano', 'Motorista'])['Horas_Parado'].sum().reset_index()
            fig_driver_line = px.line(df_driver_month, x='Mes_Ano', y='Horas_Parado', color='Motorista', markers=True,
                                      labels={'Horas_Parado': 'Horas Parado e Ligado', 'Mes_Ano': 'Mês/Ano'},
                                      title="Evolução do Tempo Parado e Ligado por Condutor")
            st.plotly_chart(fig_driver_line, use_container_width=True)

        with tab_evol3:
            st.markdown("##### Matriz de Reincidência: Total de Horas Parado/Ligado por Mês")
            pivot_matrix = df_p_filt.pivot_table(index='Motorista', columns='Mes_Ano', values='Horas_Parado', aggfunc='sum', fill_value=0)
            pivot_matrix['Total Acumulado (h)'] = pivot_matrix.sum(axis=1)
            pivot_matrix['Custo Estimado (R$)'] = pivot_matrix['Total Acumulado (h)'] * consumo_lh * preco_litro
            pivot_matrix = pivot_matrix.sort_values(by='Total Acumulado (h)', ascending=False)
            
            st.dataframe(
                pivot_matrix.style.format("{:.1f}h").format({"Custo Estimado (R$)": "R$ {:.2f}"}),
                use_container_width=True
            )

        st.markdown("---")

        # --- GRÁFICOS COMPLEMENTARES ANTERIORES (MANTIDOS INTEGRALMENTE) ---
        st.subheader("📊 Análise Geral de Ocorrências e Horários")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("##### Top Motoristas por Tempo Total Parado e Ligado (Geral)")
            m_agg = df_p_filt.groupby('Motorista').agg({'Horas_Parado': 'sum', 'Custo_Desperdicio': 'sum', 'Placa': 'count'}).reset_index()
            m_agg = m_agg.sort_values(by='Horas_Parado', ascending=False)
            fig_m = px.bar(m_agg.head(10), x='Motorista', y='Horas_Parado', text_auto='.1f', color='Custo_Desperdicio', color_continuous_scale='Reds', labels={'Horas_Parado': 'Horas Parado', 'Custo_Desperdicio': 'Custo (R$)'})
            st.plotly_chart(fig_m, use_container_width=True)

        with col_g2:
            st.markdown("##### Concentração das Ocorrências por Horário do Dia (0h-23h)")
            h_agg = df_p_filt.groupby('Hora_Inicio')['Placa'].count().reset_index()
            fig_h = px.bar(h_agg, x='Hora_Inicio', y='Placa', labels={'Hora_Inicio': 'Hora do Dia (0h-23h)', 'Placa': 'Nº Ocorrências'}, text_auto=True)
            st.plotly_chart(fig_h, use_container_width=True)

        # --- TABELA DE PARADAS CRÍTICAS DETALHADAS ---
        st.markdown("---")
        st.subheader(f"🚨 Lista Detalhada de Paradas Longas (≥ {limite_minutos} minutos)")
        criticas = df_p_filt[df_p_filt['Minutos_Parado'] >= limite_minutos].sort_values(by='Minutos_Parado', ascending=False)
        
        if not criticas.empty:
            st.dataframe(
                criticas[['Data', 'Mes_Ano', 'Placa', 'Veiculo', 'Motorista', 'Inicio', 'Final', 'Tempo_Parado', 'Custo_Desperdicio', 'Endereco']],
                column_config={
                    "Tempo_Parado": st.column_config.TextColumn("Tempo Parado"),
                    "Custo_Desperdicio": st.column_config.NumberColumn("Desperdício (R$)", format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )

        # --- GERADOR DE RELATÓRIO EXECUTIVO ---
        st.markdown("---")
        st.subheader("📝 Gerador de Relatório Executivo e de Evolução")
        if st.button("📄 Gerar Resumo Executivo"):
            top_m = q_agg.iloc[0]['Motorista'] if not q_agg.empty else "N/A"
            top_q = q_agg.iloc[0]['Qtd_Paradas_Criticas'] if not q_agg.empty else 0
            
            relatorio_txt = f"""========================================================================
RELATÓRIO DE AUDITORIA: PARADAS CRÍTICAS (≥ {limite_minutos} MIN) E REINCIDÊNCIA
========================================================================

1. RESUMO DOS INDICADORES CONSOLIDADOS DO PERÍODO
------------------------------------------------------------------------
* Meses Analisados: {', '.join(meses_unicos)}
* Total de Ocorrências Gerais: {tot_ocorrencias} paradas
* Ocorrências Críticas (≥ {limite_minutos} min): {tot_limiar} paradas ({perc_limiar:.1f}% do total)
* Tempo Total em Marcha Lenta: {int(tot_horas)} horas e {int((tot_horas%1)*60)} minutos
* Prejuízo Financeiro Acumulado: R$ {tot_custo:,.2f} ({tot_litros:,.1f} Litros)

2. RANKING DE REINCIDÊNCIA POR MOTORISTA (PARADAS ≥ {limite_minutos} MIN)
------------------------------------------------------------------------
* Maior Reincidente: {top_m} ({top_q} paradas críticas)

========================================================================
"""
            st.text_area("Pré-visualização do Relatório:", value=relatorio_txt, height=300)
            st.download_button("💾 Baixar Relatório (.txt)", data=relatorio_txt, file_name="Relatorio_Paradas_Criticas.txt", mime="text/plain")

    else:
        st.info("👈 Faça o upload dos relatórios `.pdf` ou `.xlsx` do RotaExata na barra lateral para carregar as análises.")

# ==============================================================================
# MÓDULO 2: ABASTECIMENTO E CUSTOS DE COMBUSTÍVEL (INTEGRALMENTE MANTIDO)
# ==============================================================================
else:
    st.title("⛽ Gestão de Frota - Relatório de Abastecimento e Custos")
    st.caption("Painel executivo de consumo com sanitização estatística de dados")

    uploaded_files_custos = st.sidebar.file_uploader(
        "Selecione os arquivos de Custo (.xlsx)", 
        type=["xlsx"], 
        accept_multiple_files=True
    )
    
    usar_sanitizacao = st.sidebar.toggle("Ativar Filtro Refinado de Inconsistências", value=True)

    def parse_rotaexata_custo(file):
        df_raw = pd.read_excel(file, sheet_name=0)
        df_data = df_raw.iloc[4:].copy()
        df_data.columns = df_raw.iloc[3].values
        df_clean = df_data[df_data['Data'].notna() & (df_data['Data'] != 'TOTALIZADOR')].copy()
        
        def clean_num(val):
            if pd.isna(val): return None
            s = str(val).replace('\xa0', '').replace('R$', '').replace('Km', '').replace('L', '').replace(' ', '').strip()
            s = s.replace('.', '').replace(',', '.') if ',' in s else s
            try: return float(s)
            except: return None
                
        num_cols = ['Km inicial', 'Km final', 'Km rodado', 'Litros abastecidos', 'Litros consumidos', 'Capacidade do tanque', 'Custo por litro', 'Custo total', 'Média km/litro', 'Média custo/km']
        for col in num_cols:
            if col in df_clean.columns: df_clean[col] = df_clean[col].apply(clean_num)
        df_clean['Data'] = pd.to_datetime(df_clean['Data'], format='%d/%m/%Y', errors='coerce')
        return df_clean

    if uploaded_files_custos:
        df_c_list = [parse_rotaexata_custo(f) for f in uploaded_files_custos]
        df_c_raw = pd.concat(df_c_list, ignore_index=True)
        
        df_c_raw['Km_Calculado'] = df_c_raw['Km final'] - df_c_raw['Km inicial']
        df_c_raw['KmL_Real_Abastecido'] = df_c_raw['Km_Calculado'] / df_c_raw['Litros abastecidos']
        df_c_raw['Custo_Km_Real'] = df_c_raw['Custo total'] / df_c_raw['Km_Calculado']

        def diagnosticar_registro(row):
            motivos = []
            if pd.isna(row['Km_Calculado']) or row['Km_Calculado'] <= 0 or row['Km_Calculado'] > 1200:
                motivos.append("Odômetro Inválido/Exagero")
            if pd.isna(row['Custo por litro']) or not (4.0 <= row['Custo por litro'] <= 9.0):
                motivos.append("Preço/L Atípico")
            kml = row['KmL_Real_Abastecido']
            if pd.isna(kml) or not (3.0 <= kml <= 22.0):
                motivos.append(f"Média Impossível ({kml:.1f} km/L)")
            return " | ".join(motivos) if motivos else "VÁLIDO"

        df_c_raw['Status_Auditoria'] = df_c_raw.apply(diagnosticar_registro, axis=1)
        df_c_validos = df_c_raw[df_c_raw['Status_Auditoria'] == "VÁLIDO"].copy()
        df_c_work = df_c_validos if usar_sanitizacao else df_c_raw.copy()

        # KPIs
        st.subheader("📌 Indicadores Consolidados de Consumo")
        n_a = len(df_c_work)
        c_tot = df_c_work['Custo total'].sum()
        km_tot = df_c_work['Km_Calculado'].sum()
        lit_tot = df_c_work['Litros abastecidos'].sum()
        med_kml = df_c_work['KmL_Real_Abastecido'].mean()
        std_kml = df_c_work['KmL_Real_Abastecido'].std()
        margem_kml = 1.96 * (std_kml / np.sqrt(n_a)) if n_a > 0 else 0

        kc1, kc2, kc3, kc4 = st.columns(4)
        kc1.metric("Investimento Total", f"R$ {c_tot:,.2f}")
        kc2.metric("Km Total Rodado", f"{km_tot:,.0f} km")
        kc3.metric("Volume Abastecido", f"{lit_tot:,.1f} L")
        kc4.metric("Consumo Médio Real", f"{med_kml:.2f} km/L", delta=f"± {margem_kml:.2f} km/L")

        col_cl, col_cr = st.columns(2)
        with col_cl:
            st.subheader("💰 Custo por Veículo (Placa)")
            fig_c = px.bar(df_c_work.groupby('Placa')['Custo total'].sum().reset_index().sort_values(by='Custo total', ascending=False), x='Placa', y='Custo total', text_auto='.2f')
            st.plotly_chart(fig_c, use_container_width=True)
        with col_cr:
            st.subheader("🏆 Média Real Sanitizada (km/L)")
            fig_k = px.bar(df_c_work.groupby('Placa')['KmL_Real_Abastecido'].mean().reset_index().sort_values(by='KmL_Real_Abastecido', ascending=False), x='Placa', y='KmL_Real_Abastecido', text_auto='.2f')
            st.plotly_chart(fig_k, use_container_width=True)
    else:
        st.info("👈 Envie os relatórios de Custo em Excel na barra lateral.")
