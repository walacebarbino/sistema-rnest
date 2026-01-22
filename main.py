# --- ABA 2: CURVA S COM INDICADORES ACIMA (CORRIGIDA) ---
    elif aba == "📊 CURVA S":
        st.subheader("📈 Evolução Acumulada das Disciplinas")
        
        # Função robusta para gerar os dados da curva
        def gerar_curva_data(df):
            if df is None or df.empty:
                return None
            df_c = df.copy()
            # Garante que as colunas existam antes de converter
            cols_datas = [c for c in ['PREVISTO', 'DATA FIM PROG', 'DATA MONT'] if c in df_c.columns]
            for c in cols_datas:
                df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
            
            datas = pd.concat([df_c[c] for c in cols_datas]).dropna()
            if datas.empty:
                return None
            
            eixo_x = pd.date_range(start=datas.min(), end=datas.max(), freq='D')
            df_res = pd.DataFrame(index=eixo_x)
            if 'PREVISTO' in df_c.columns:
                df_res['PREVISTO'] = [len(df_c[df_c['PREVISTO'] <= d]) for d in eixo_x]
            if 'DATA FIM PROG' in df_c.columns:
                df_res['PROGRAMADO'] = [len(df_c[df_c['DATA FIM PROG'] <= d]) for d in eixo_x]
            if 'DATA MONT' in df_c.columns:
                df_res['REALIZADO'] = [len(df_c[df_c['DATA MONT'] <= d]) for d in eixo_x]
            return df_res

        # Criando as duas colunas fixas
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("#### ⚡ ELÉTRICA")
            if not df_ele.empty:
                p_ele = (len(df_ele[df_ele['STATUS']=='MONTADO'])/len(df_ele))*100
                st.write(f"Progresso: {p_ele:.1f}%")
                st.progress(p_ele/100)
                
                df_res_ele = gerar_curva_data(df_ele)
                if df_res_ele is not None:
                    st.plotly_chart(px.line(df_res_ele, title="Curva S - ELÉTRICA", template="plotly_white"), use_container_width=True)
                else:
                    st.warning("⚠️ Elétrica: Sem datas para gerar o gráfico.")
            else:
                st.error("Planilha de Elétrica não encontrada ou vazia.")

        with col_g2:
            st.markdown("#### 🔬 INSTRUMENTAÇÃO")
            if not df_ins.empty:
                p_ins = (len(df_ins[df_ins['STATUS']=='MONTADO'])/len(df_ins))*100
                st.write(f"Progresso: {p_ins:.1f}%")
                st.progress(p_ins/100)
                
                df_res_ins = gerar_curva_data(df_ins)
                if df_res_ins is not None:
                    st.plotly_chart(px.line(df_res_ins, title="Curva S - INSTRUMENTAÇÃO", template="plotly_white"), use_container_width=True)
                else:
                    st.warning("⚠️ Instrumentação: Sem datas para gerar o gráfico.")
            else:
                st.error("Planilha de Instrumentação não encontrada ou vazia.")
