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
    st.caption("Diagnóstico de combustível desperdiçado, ranking de infratores e análise de paradas atípicas do RotaExata")

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

        df = pd.DataFrame(records)
        return df

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
        df_parado['Hora_Inicio'] = pd.to_datetime(df_parado['Inicio'], format='%H:%M:%S', errors='coerce').dt.hour

        # --- FILTROS ---
        motoristas_unicos = sorted(df_parado['Motorista'].dropna().unique())
        sel_motoristas = st.sidebar.multiselect("Filtrar por Motorista", options=motoristas_unicos, default=motoristas_unicos)
        df_p_filt = df_parado[df_parado['Motorista'].isin(sel_motoristas)].copy()

        # --- KPIS ---
        st.subheader("📌 Indicadores do Prejuízo por Carro Parado e Ligado")
        k1, k2, k3, k4, k5 = st.columns(5)
        
        tot_ocorrencias = len(df_p_filt)
        tot_horas = df_p_filt['Horas_Parado'].sum()
        tot_litros = df_p_filt['Litros_Desperdiçados'].sum()
        tot_custo = df_p_filt['Custo_Desperdicio'].sum()
        media_minutos = df_p_filt['Minutos_Parado'].mean() if tot_ocorrencias > 0 else 0

        k1.metric("Ocorrências Registradas", f"{tot_ocorrencias} paradas")
        k2.metric("Tempo Total Parado Ligado", f"{int(tot_horas)}h {int((tot_horas%1)*60)}min")
        k3.metric("Combustível Perdido", f"{tot_litros:,.1f} L")
        k4.metric("Prejuízo Estimado", f"R$ {tot_custo:,.2f}")
        k5.metric("Média por Parada", f"{media_minutos:.1f} min")

        st.markdown("---")

        # --- GRÁFICOS ---
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("👤 Top Motoristas em Tempo Parado e Ligado")
            m_agg = df_p_filt.groupby('Motorista').agg({'Horas_Parado': 'sum', 'Custo_Desperdicio': 'sum', 'Placa': 'count'}).reset_index()
            m_agg = m_agg.sort_values(by='Horas_Parado', ascending=False)
            fig_m = px.bar(m_agg.head(10), x='Motorista', y='Horas_Parado', text_auto='.1f', color='Custo_Desperdicio', color_continuous_scale='Reds', labels={'Horas_Parado': 'Horas Parado', 'Custo_Desperdicio': 'Custo (R$)'})
            st.plotly_chart(fig_m, use_container_width=True)

        with col_g2:
            st.subheader("⏰ Distribuição das Ocorrências por Horário do Dia")
            h_agg = df_p_filt.groupby('Hora_Inicio')['Placa'].count().reset_index()
            fig_h = px.bar(h_agg, x='Hora_Inicio', y='Placa', labels={'Hora_Inicio': 'Hora do Dia (0h-23h)', 'Placa': 'Nº Ocorrências'}, text_auto=True)
            st.plotly_chart(fig_h, use_container_width=True)

        # --- TABELA DE PARADAS CRÍTICAS ---
        st.markdown("---")
        st.subheader("🚨 Paradas Mais Longas / Críticas (> 30 minutos)")
        criticas = df_p_filt[df_p_filt['Minutos_Parado'] >= 30].sort_values(by='Minutos_Parado', ascending=False)
        
        if not criticas.empty:
            st.warning(f"Foram identificadas {len(criticas)} paradas com duração superior a 30 minutos contínuos com motor ligado!")
            st.dataframe(
                criticas[['Data', 'Placa', 'Veiculo', 'Motorista', 'Inicio', 'Final', 'Tempo_Parado', 'Custo_Desperdicio', 'Endereco']],
                column_config={
                    "Tempo_Parado": st.column_config.TextColumn("Tempo Parado"),
                    "Custo_Desperdicio": st.column_config.NumberColumn("Desperdício (R$)", format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.success("✅ Nenhuma parada contínua superior a 30 minutos foi identificada.")

        # --- GERADOR DE RELATÓRIO EXECUTIVO ---
        st.markdown("---")
        st.subheader("📝 Gerador de Relatório Executivo de Idling")
        if st.button("📄 Gerar Resumo Executivo"):
            top_m = m_agg.iloc[0]['Motorista'] if not m_agg.empty else "N/A"
            top_h = m_agg.iloc[0]['Horas_Parado'] if not m_agg.empty else 0
            
            relatorio_txt = f"""========================================================================
RELATÓRIO DE AUDITORIA: VEÍCULOS PARADOS COM MOTOR LIGADO (IDLING)
========================================================================

1. RESUMO DOS INDICADORES CONSOLIDADOS
------------------------------------------------------------------------
* Total de Ocorrências: {tot_ocorrencias} paradas
* Tempo Total de Motor Ligado Parado: {int(tot_horas)} horas e {int((tot_horas%1)*60)} minutos
* Média de Duração por Ocorrência: {media_minutos:.1f} minutos por parada

2. IMPACTO FINANCEIRO E AMBIENTAL
------------------------------------------------------------------------
* Parâmetro do Combustível: R$ {preco_litro:.2f} / Litro
* Taxa de Consumo em Marcha Lenta: {consumo_lh:.2f} Litros / Hora
* Volume Total Desperdiçado: {tot_litros:,.1f} Litros de combustível
* Prejuízo Financeiro Acumulado: R$ {tot_custo:,.2f}

3. RANKING DE CONDUTORES
------------------------------------------------------------------------
* Maior Infrator Individual: {top_m} ({top_h:.2f} horas com motor ligado)
* Paradas Críticas (>30 min contínuos): {len(criticas)} ocorrências

========================================================================
"""
            st.text_area("Pré-visualização do Relatório:", value=relatorio_txt, height=300)
            st.download_button("💾 Baixar Relatório (.txt)", data=relatorio_txt, file_name="Relatorio_Carro_Parado_Ligado.txt", mime="text/plain")

    else:
        st.info("👈 Faça o upload dos relatórios `.pdf` ou `.xlsx` extraídos do RotaExata na barra lateral esquerda.")

# ==============================================================================
# MÓDULO 2: ABASTECIMENTO E CUSTOS DE COMBUSTÍVEL
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
