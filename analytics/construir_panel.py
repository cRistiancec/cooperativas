#!/usr/bin/env python3
"""Construye el panel cooperativa-mes (S1-S3) EXCLUSIVAMENTE desde master_data/ del repo.
Uso: python construir_panel.py <ruta_repo> <dir_salida>
Segmento: el del repo es RETROACTIVO (ver C-01); se conserva como `segmento_repo` y se marca.
`segmento_norma_activos` es solo un proxy diagnóstico (umbrales vigentes SEPS aplicados a activos del mes), NO oficial."""
import sys, json, numpy as np, pandas as pd
repo, out = sys.argv[1].rstrip('/')+'/master_data/', sys.argv[2].rstrip('/')+'/'
# Lectura por lotes (balance = ~25 M de filas): solo cuentas de hasta 4 dígitos y S1-S3
# point-in-time, que es todo lo que usa el panel.
import pyarrow.parquet as pq
_cols = ['cooperativa','fecha','codigo','valor','segmento','segmento_historico','segmento_historico_estimado']
_pf = pq.ParquetFile(repo+'balance.parquet'); _cols = [c for c in _cols if c in _pf.schema_arrow.names]
_partes = []
for rb in _pf.iter_batches(batch_size=2_000_000, columns=_cols):
    d = rb.to_pandas()
    d['codigo'] = d.codigo.astype(str)
    d = d[d.codigo.str.len() <= 4]
    seg_col = 'segmento_historico' if 'segmento_historico' in d else 'segmento'
    d = d[d[seg_col].astype(str).isin(['SEGMENTO 1','SEGMENTO 2','SEGMENTO 3'])]
    d['cooperativa'] = d.cooperativa.astype(str)
    d['segmento'] = d['segmento'].astype(str)
    if 'segmento_historico' in d:
        d['segmento_historico'] = d.segmento_historico.astype(str)
    _partes.append(d)
B = pd.concat(_partes, ignore_index=True); del _partes
B['cooperativa'] = B.cooperativa.astype(str)
# Segmento POINT-IN-TIME acoplado en la ingesta (segmento_historico). NO se filtra por el
# segmento retroactivo: una cooperativa hoy en S4/S5 pudo ser S3 en 2019.
if 'segmento_historico' in B.columns:
    B['segmento'] = B.segmento_historico.astype(str)
    B['segmento_retroactivo'] = B.segmento_historico_estimado.astype(bool)
else:
    print('AVISO: balance sin segmento_historico -> segmento retroactivo (C-01)')
    B['segmento_retroactivo'] = True
B = B[B.segmento.isin(['SEGMENTO 1','SEGMENTO 2','SEGMENTO 3']) & ~B.cooperativa.str.upper().str.startswith('VT_TOTAL')].copy()
seg = B.drop_duplicates(['cooperativa','fecha'])[['cooperativa','fecha','segmento','segmento_retroactivo']].copy()
assert not B.duplicated(['cooperativa','fecha','codigo']).any(), 'duplicados'
def s(codes):                      # suma por coop-fecha de una lista de códigos
    return B[B.codigo.isin(codes)].groupby(['cooperativa','fecha']).valor.sum()
cod_impr = [str(c) for c in range(1425,1490) if str(c) not in ('1473','1475','1477')]
cod_cart = [str(c) for c in range(1401,1490)]
V = {'activos':s(['1']),'pasivos':s(['2']),'patrimonio':s(['3']),'fondos_disponibles':s(['11']),
 'cartera_neta_14':s(['14']),'cartera_improductiva':s(cod_impr),'provisiones':-s(['1499']),
 'dep_vista':s(['2101']),'dep_plazo':s(['2103']),'obligaciones_publico':s(['21']),
 'obligaciones_financieras':s(['26']),'ingresos_ytd':s(['5']),'gastos_ytd':s(['4']),
 'gastos_operacion_ytd':s(['45']),'ingresos_oper_ytd':s(['51','52','53','54','55']),
 'intereses_causados_ytd':s(['41']),'provisiones_gasto_ytd':s(['44'])}
cb = s([c for c in cod_cart if c in set(B.codigo.unique())]); V['cartera_bruta'] = cb + V['provisiones']*0  # bruta = 1401..1489
P = pd.DataFrame(V).fillna(0).reset_index()
P = P.merge(seg, on=['cooperativa','fecha'], how='left').sort_values(['cooperativa','fecha'])
P['cartera_bruta'] = P['cartera_bruta'].where(P['cartera_bruta']>0)
# --- flujos mensuales y 12m a partir de saldos YTD (desacumulación; enero = YTD) ---
def flujo(col):
    prev = P.groupby('cooperativa')[col].shift(1)
    nueva = P.fecha.dt.month==1
    cont = P.groupby('cooperativa').fecha.diff().dt.days.between(27,32)
    m = np.where(nueva, P[col], np.where(cont, P[col]-prev, np.nan))
    return pd.Series(m, index=P.index)
for c in ['ingresos','gastos','gastos_operacion','ingresos_oper']:
    P[c+'_mes'] = flujo(c+'_ytd')
P['resultado_mes'] = P.ingresos_mes - P.gastos_mes
for c in ['resultado','ingresos_oper','gastos_operacion']:
    P[c+'_12m'] = P.groupby('cooperativa')[c+'_mes'].transform(lambda x: x.rolling(12,min_periods=12).sum())
P['resultado_ytd'] = P.ingresos_ytd - P.gastos_ytd
# --- reindexar a calendario mensual para rezagos t-12 por fecha (no por posición) ---
P = P.set_index(['cooperativa','fecha'])
def lag12(col):
    idx = P.index.to_frame(index=False); idx['fecha'] = idx.fecha - pd.offsets.MonthEnd(12)
    return pd.Series(P[col].reindex(pd.MultiIndex.from_frame(idx)).values, index=P.index)
P['activos_l12'] = lag12('activos'); P['patrimonio_l12']=lag12('patrimonio')
P = P.reset_index()
den = lambda a: a.where(a>0)
P['solvencia_proxy'] = P.patrimonio/den(P.activos)*100
P['liquidez_vista'] = P.fondos_disponibles/den(P.dep_vista)*100
P['liquidez_total'] = P.fondos_disponibles/den(P.obligaciones_publico)*100
P['morosidad'] = P.cartera_improductiva/den(P.cartera_bruta)*100
P['cobertura'] = P.provisiones/den(P.cartera_improductiva)*100
P['roa_12m'] = P.resultado_12m/den((P.activos+P.activos_l12)/2)*100
P['roe_12m'] = P.resultado_12m/den((P.patrimonio+P.patrimonio_l12)/2)*100
P['eficiencia'] = P.gastos_operacion_12m/den(P.ingresos_oper_12m)*100
P['crec_activos_12m'] = (P.activos/den(P.activos_l12)-1)*100
P['ln_activos'] = np.log(den(P.activos))
# diagnóstico (NO oficial)
P['segmento_norma_activos'] = np.select([P.activos>80e6,P.activos>20e6,P.activos>5e6],['SEGMENTO 1','SEGMENTO 2','SEGMENTO 3'],'<=5M')
P = P.rename(columns={'segmento':'segmento_repo'})
P = P.rename(columns={'segmento_retroactivo':'segmento_repo_retroactivo'})   # False = tomado de dim_segmento_historico (point-in-time)
# --- eventos de salida (sólo observables: última fecha reportada) ---
fin = P.groupby('cooperativa').fecha.max(); fmax = P.fecha.max()
P['ultima_obs'] = P.fecha.eq(P.cooperativa.map(fin)); P['dejo_de_reportar'] = P.ultima_obs & (P.fecha<fmax)
# --- indicadores oficiales SEPS (2020+) para reconciliación ---
I = pd.read_parquet(repo+'indicadores.parquet'); I = I[I.codigo.isin(['MOR_TOT','ROA','ROE','LIQ','COB_TOT','SUF_PAT'])]
W = I.pivot_table(index=['cooperativa','fecha'],columns='codigo',values='valor',aggfunc='first').add_prefix('seps_').reset_index()
W['cooperativa']=W.cooperativa.astype(str)
P = P.merge(W,on=['cooperativa','fecha'],how='left')
P = P.drop(columns=['ingresos_ytd','gastos_ytd','gastos_operacion_ytd','ingresos_oper_ytd','intereses_causados_ytd','provisiones_gasto_ytd','activos_l12','patrimonio_l12','cartera_neta_14'])
P.to_parquet(out+'panel_cooperativas_S1S3.parquet',index=False); P.to_csv(out+'panel_cooperativas_S1S3.csv.gz',index=False)
# --- reporte de calidad ---
q = {'filas':len(P),'cooperativas':int(P.cooperativa.nunique()),'fecha_min':str(P.fecha.min().date()),'fecha_max':str(P.fecha.max().date()),
 'dup_coop_fecha':int(P.duplicated(['cooperativa','fecha']).sum()),
 'nulos_pct':{c:round(P[c].isna().mean()*100,2) for c in ['solvencia_proxy','liquidez_vista','morosidad','roa_12m','roe_12m','eficiencia','crec_activos_12m']},
 'morosidad_fuera_0_100':int(((P.morosidad<0)|(P.morosidad>100)).sum()),'solvencia_negativa':int((P.solvencia_proxy<0).sum())}
for a,b in [('morosidad','seps_MOR_TOT'),('cobertura','seps_COB_TOT'),('roa_12m','seps_ROA'),('roe_12m','seps_ROE'),('liquidez_vista','seps_LIQ')]:
    d = P[[a,b]].dropna().copy(); d[b] = d[b]*100   # los indicadores SEPS vienen como razón (0-1)
    
    q['recon_'+a+'_vs_'+b] = {'n':len(d),'corr':round(d[a].corr(d[b]),4) if len(d)>2 else None,'mediana_dif_abs':round((d[a]-d[b]).abs().median(),4) if len(d) else None}
json.dump(q,open(out+'calidad_panel.json','w'),indent=1,ensure_ascii=False); print(json.dumps(q,indent=1,ensure_ascii=False))
