import webbrowser
from threading import Timer
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output



from sqlalchemy import create_engine

USUARIO = "avnadmin"
PASSWORD = "AVNS_B-5xRIf0MrNHW_zHMX1"          
HOST = "mysql-cafeteria-kddindividual.k.aivencloud.com"
PORT = "17967"

# Conexión correcta con SSL para Aiven
engine_prod = create_engine(
    f"mysql+pymysql://{USUARIO}:{PASSWORD}@{HOST}:{PORT}/SistemaCafeteria_Produccion",
    connect_args={"ssl": {"ssl_mode": "REQUIRED"}}
)

engine_result = create_engine(
    f"mysql+pymysql://{USUARIO}:{PASSWORD}@{HOST}:{PORT}/SistemaCafeteria_Resultados",
    connect_args={"ssl": {"ssl_mode": "REQUIRED"}}
)
def procesar_kdd():
    query = """
    SELECT
        YEAR(V.fecha)                                          AS anio,
        MONTH(V.fecha)                                         AS mes,
        P.categoria                                            AS categoria_platillo,
        SUM(DV.cantidad)                                       AS platillos_vendidos,
        SUM(DV.importe)                                        AS venta_bruta,
        SUM(DV.cantidad * CI.costo_operativo_por_unidad)       AS costo_insumos,
        SUM(DV.importe) - SUM(DV.cantidad * CI.costo_operativo_por_unidad) AS utilidad_neta
    FROM SistemaCafeteria_Produccion.Ventas V
    JOIN SistemaCafeteria_Produccion.Detalle_Ventas   DV  ON DV.venta_id = V.id_venta
    JOIN SistemaCafeteria_Produccion.Platillos        P   ON P.id_platillo = DV.platillo_id
    JOIN SistemaCafeteria_Produccion.Costos_Insumos   CI  ON DATE(CI.fecha_costo) = DATE(V.fecha)
    GROUP BY YEAR(V.fecha), MONTH(V.fecha), P.categoria
    ORDER BY anio, mes;
    """
    df = pd.read_sql(query, engine_prod)
    with engine_result.begin() as con:
        con.execute(text("TRUNCATE TABLE Resumen_Cafeteria_KDD;"))
    df.to_sql("Resumen_Cafeteria_KDD", con=engine_result, if_exists="append", index=False)
    print(f"[KDD OK] {len(df)} registros migrados a Resumen_Cafeteria_KDD.")
    return df

try:
    procesar_kdd()
    PIPELINE_OK  = True
    PIPELINE_MSG = " Pipeline KDD ejecutado. Resumen_Cafeteria_KDD actualizado y listo para análisis."
except Exception as e:
    PIPELINE_OK  = False
    PIPELINE_MSG = f" Error en pipeline KDD: {e}"

def cargar_kdd():
    """ÚNICA fuente de datos para las 12 gráficas: la tabla de Resultados KDD."""
    df = pd.read_sql(
        "SELECT anio,mes,categoria_platillo,platillos_vendidos,venta_bruta,costo_insumos,utilidad_neta "
        "FROM Resumen_Cafeteria_KDD ORDER BY anio,mes;", engine_result)
    df["periodo"]    = df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
    df["trimestre"]  = ((df["mes"] - 1) // 3) + 1
    return df

def total_kdd():
    q = "SELECT COUNT(*) AS total FROM Resumen_Cafeteria_KDD;"
    return pd.read_sql(q, engine_result).iloc[0]["total"]


BG_APP   = '#f1f5f9'
CARD     = '#ffffff'
BORDE    = '#e2e8f0'
TXT      = '#0f172a'
MUTED    = '#64748b'

ESTILO_APP = {
    'fontFamily': "'Segoe UI', Arial", 'backgroundColor': BG_APP,
    'color': TXT, 'minHeight': '100vh', 'padding': '0'
}

COLOR_TABS = {
    'tendencias':   '#2563eb',
    'rentabilidad': '#059669',
    'operacion':    '#d97706',
    'riesgo':       '#dc2626',
}


def asistente_ia(estado, titulo, diagnostico, puntos):
    paleta = {
        'bien':    {'bg': '#ecfdf5', 'borde': '#10b981', 'tit': '#047857', 'txt': '#065f46', 'icono': '✅', 'etiqueta': 'Por qué está bien'},
        'mejorar': {'bg': '#fffbeb', 'borde': '#f59e0b', 'tit': '#b45309', 'txt': '#78350f', 'icono': '🛠️', 'etiqueta': 'Cómo mejorarlo'},
        'critico': {'bg': '#fef2f2', 'borde': '#ef4444', 'tit': '#b91c1c', 'txt': '#7f1d1d', 'icono': '🚨', 'etiqueta': 'Acción urgente'},
    }
    p = paleta[estado]
    return html.Div(style={
        'backgroundColor': p['bg'], 'border': f'1.5px solid {p["borde"]}',
        'borderRadius': '10px', 'padding': '12px 16px', 'marginTop': '12px'
    }, children=[
        html.Div([
            html.Span(p['icono'], style={'marginRight': '6px'}),
            html.Span(titulo, style={'fontWeight': '700', 'fontSize': '13px', 'color': p['tit']}),
        ]),
        html.P(diagnostico, style={'fontSize': '12px', 'color': p['txt'], 'margin': '6px 0'}),
        html.Div(p['etiqueta'], style={'fontSize': '10px', 'fontWeight': '700',
                                        'color': p['tit'], 'textTransform': 'uppercase',
                                        'letterSpacing': '0.5px', 'marginTop': '6px'}),
        html.Ul([html.Li(pt, style={'fontSize': '12px', 'color': p['txt'], 'margin': '3px 0'})
                 for pt in puntos], style={'margin': '4px 0 0', 'paddingLeft': '18px'})
    ])

def tarjeta(titulo_obj, gid, fig, asistente):
    return html.Div(style={
        'backgroundColor': CARD, 'border': f'1px solid {BORDE}', 'borderRadius': '14px',
        'padding': '16px', 'boxShadow': '0 1px 3px rgba(0,0,0,0.04)'
    }, children=[
        html.P(titulo_obj, style={'fontWeight': '700', 'fontSize': '13px', 'color': TXT, 'margin': '0 0 8px'}),
        dcc.Graph(id=gid, figure=fig, config={'displayModeBar': False}),
        html.Div(id=f"ai-{gid}", children=asistente),
    ])


app = dash.Dash(__name__, title="Cafetería — Panel de Objetivos KDD")
server = app.server
app.layout = html.Div(style=ESTILO_APP, children=[

    # NAVBAR
    html.Div(style={'backgroundColor': CARD, 'borderBottom': f'1px solid {BORDE}',
                    'padding': '18px 32px', 'display': 'flex', 'justifyContent': 'space-between',
                    'alignItems': 'center'}, children=[
        html.Div([
            html.Span(" ", style={'fontSize': '22px'}),
            html.Span("Panel de Objetivos KDD — Cafetería", style={'fontSize': '19px', 'fontWeight': '800'}),
        ]),
        html.Div(id='pipeline-status', style={'fontSize': '12px'}),
    ]),

    html.Div(style={'padding': '24px 32px'}, children=[

        html.Div(id='resumen-kdd', style={'marginBottom': '20px'}),

        # FILTROS
        html.Div(style={'backgroundColor': CARD, 'border': f'1px solid {BORDE}', 'borderRadius': '12px',
                        'padding': '16px 20px', 'marginBottom': '22px', 'display': 'flex', 'gap': '24px',
                        'alignItems': 'flex-end'}, children=[
            html.Div([
                html.Label("Año", style={'fontSize': '11px', 'color': MUTED, 'fontWeight': '700'}),
                dcc.Dropdown(id='dd-anio', options=[], value='Todos', clearable=False, style={'width': '220px'})
            ]),
            html.Div([
                html.Label("Categoría del menú", style={'fontSize': '11px', 'color': MUTED, 'fontWeight': '700'}),
                dcc.Dropdown(id='dd-categoria', options=[], value='Todos', clearable=False, style={'width': '260px'})
            ]),
            html.Div("Fuente de datos: tabla Resumen_Cafeteria_KDD (Resultados KDD).",
                     style={'fontSize': '11px', 'color': MUTED, 'fontStyle': 'italic', 'marginLeft': 'auto', 'maxWidth': '360px'})
        ]),

        html.Div(id='kpis', style={'display': 'flex', 'gap': '16px', 'marginBottom': '24px'}),

        # TABS — 4 categorías de objetivos, 3 gráficas cada una = 12
        dcc.Tabs(id='tabs', value='tendencias', children=[
            dcc.Tab(label=' Tendencias y Proyección',   value='tendencias',   style={'fontSize': '13px'}, selected_style={'fontSize': '13px', 'fontWeight': '700', 'borderTop': f'3px solid {COLOR_TABS["tendencias"]}'}),
            dcc.Tab(label=' Rentabilidad por Categoría', value='rentabilidad', style={'fontSize': '13px'}, selected_style={'fontSize': '13px', 'fontWeight': '700', 'borderTop': f'3px solid {COLOR_TABS["rentabilidad"]}'}),
            dcc.Tab(label=' Operación y Ticket',         value='operacion',    style={'fontSize': '13px'}, selected_style={'fontSize': '13px', 'fontWeight': '700', 'borderTop': f'3px solid {COLOR_TABS["operacion"]}'}),
            dcc.Tab(label=' Estacionalidad y Riesgo',    value='riesgo',       style={'fontSize': '13px'}, selected_style={'fontSize': '13px', 'fontWeight': '700', 'borderTop': f'3px solid {COLOR_TABS["riesgo"]}'}),
        ]),
        html.Div(id='tab-content', style={'marginTop': '22px'}),

        html.Div(style={'height': '30px'})
    ])
])



@app.callback(
    [Output('pipeline-status', 'children'),
     Output('resumen-kdd',     'children'),
     Output('kpis',            'children'),
     Output('dd-anio',         'options'),
     Output('dd-categoria',    'options')],
    [Input('dd-anio', 'value'), Input('dd-categoria', 'value')]
)
def actualizar_encabezado(anio_v, categoria_v):
    pip = html.Span(PIPELINE_MSG, style={'color': '#059669' if PIPELINE_OK else '#dc2626', 'fontWeight': '600'})

    try:
        n = total_kdd()
        resumen = html.Div(f" La tabla Resumen_Cafeteria_KDD contiene {n:,} registros (combinaciones año · mes · categoría) generados por el proceso KDD.",
                           style={'fontSize': '12px', 'color': MUTED})
    except Exception as ex:
        resumen = html.Div(f"No se pudo leer Resumen_Cafeteria_KDD: {ex}", style={'color': '#dc2626'})

    try:
        df = cargar_kdd()
    except Exception:
        return pip, resumen, [], [], []

    anios      = sorted(df['anio'].unique())
    categorias = sorted(df['categoria_platillo'].unique())
    opt_a = [{'label': 'Todos los años', 'value': 'Todos'}] + [{'label': str(a), 'value': a} for a in anios]
    opt_c = [{'label': 'Todas las categorías', 'value': 'Todos'}] + [{'label': c, 'value': c} for c in categorias]

    df_f = df.copy()
    if anio_v and anio_v != 'Todos':
        df_f = df_f[df_f['anio'] == int(anio_v)]
    if categoria_v and categoria_v != 'Todos':
        df_f = df_f[df_f['categoria_platillo'] == categoria_v]

    vt, ct, ut = df_f['venta_bruta'].sum(), df_f['costo_insumos'].sum(), df_f['utilidad_neta'].sum()
    uv = df_f['platillos_vendidos'].sum()
    margen = (ut / vt * 100) if vt > 0 else 0

    def kpi(label, valor, color):
        return html.Div(style={'flex': '1', 'backgroundColor': CARD, 'border': f'1px solid {BORDE}',
                               'borderRadius': '12px', 'padding': '16px', 'borderLeft': f'4px solid {color}'},
                        children=[html.Div(label, style={'fontSize': '11px', 'color': MUTED, 'fontWeight': '700'}),
                                  html.Div(valor, style={'fontSize': '20px', 'fontWeight': '800', 'color': TXT, 'marginTop': '4px'})])
    kpis = [
        kpi("Venta Bruta",    f"${vt:,.0f}",     '#2563eb'),
        kpi("Costo Insumos",  f"${ct:,.0f}",     '#dc2626'),
        kpi("Utilidad Neta",  f"${ut:,.0f}",     '#059669' if ut >= 0 else '#dc2626'),
        kpi("Margen Neto",    f"{margen:,.1f}%", '#7c3aed'),
        kpi("Platillos Vendidos", f"{uv:,.0f}",  '#d97706'),
    ]
    return pip, resumen, kpis, opt_a, opt_c



@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'), Input('dd-anio', 'value'), Input('dd-categoria', 'value')]
)
def render_tab(tab, anio_v, categoria_v):
    T = "plotly_white"
    BG = {'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': 'rgba(0,0,0,0)', 'height': 300,
          'margin': dict(l=10, r=10, t=40, b=10)}

    try:
        df = cargar_kdd()
    except Exception as ex:
        return html.Div(f"No se pudieron cargar datos de Resumen_Cafeteria_KDD: {ex}", style={'color': '#dc2626'})

    if df.empty:
        return html.Div("Aún no hay datos en Resumen_Cafeteria_KDD. Ejecuta el pipeline KDD primero.", style={'color': '#dc2626'})

    df_f = df.copy()
    if anio_v and anio_v != 'Todos':
        df_f = df_f[df_f['anio'] == int(anio_v)]
    if categoria_v and categoria_v != 'Todos':
        df_f = df_f[df_f['categoria_platillo'] == categoria_v]
    if df_f.empty:
        return html.Div("No hay registros para ese filtro.", style={'color': '#dc2626'})

    grid = lambda cards: html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr 1fr', 'gap': '20px'}, children=cards)


    if tab == 'tendencias':
        # OBJ 1 — Venta Bruta vs Costo de Insumos
        d1 = df_f.groupby('periodo')[['venta_bruta', 'costo_insumos']].sum().reset_index()
        f1 = go.Figure()
        f1.add_trace(go.Scatter(x=d1['periodo'], y=d1['venta_bruta'], name='Venta Bruta', line=dict(color='#2563eb', width=2.5)))
        f1.add_trace(go.Scatter(x=d1['periodo'], y=d1['costo_insumos'], name='Costo Insumos', line=dict(color='#dc2626', width=2.5)))
        f1.update_layout(title="Obj 1 — Venta Bruta vs Costo de Insumos", template=T, **BG)
        if len(d1) >= 2 and d1['venta_bruta'].iloc[0] > 0 and d1['costo_insumos'].iloc[0] > 0:
            cre_v = (d1['venta_bruta'].iloc[-1] / d1['venta_bruta'].iloc[0] - 1) * 100
            cre_c = (d1['costo_insumos'].iloc[-1] / d1['costo_insumos'].iloc[0] - 1) * 100
        else:
            cre_v = cre_c = 0
        if cre_v > cre_c:
            ai1 = asistente_ia('bien', 'Ingresos crecen más rápido que los costos',
                f"La venta bruta creció {cre_v:.1f}% en el período contra {cre_c:.1f}% del costo de insumos.",
                ["Esto significa que cada peso adicional vendido deja más margen que antes.",
                 "El modelo de precios y compras actual está funcionando: consérvalo como referencia."])
        else:
            ai1 = asistente_ia('mejorar', 'Los costos crecen más rápido que las ventas',
                f"El costo de insumos subió {cre_c:.1f}% frente a un {cre_v:.1f}% de crecimiento en ventas.",
                ["Renegocia precios con proveedores o busca alternativas de compra por volumen.",
                 "Revisa si hay merma o desperdicio de insumos que esté inflando el costo.",
                 "Considera ajustar precios de venta en los platillos más afectados."])

        # OBJ 2 — Margen de Utilidad % mensual
        d2 = df_f.groupby('periodo')[['venta_bruta', 'utilidad_neta']].sum().reset_index()
        d2['margen'] = np.where(d2['venta_bruta'] > 0, d2['utilidad_neta'] / d2['venta_bruta'] * 100, 0)
        f2 = px.line(d2, x='periodo', y='margen', title="Obj 2 — Margen de Utilidad Mensual (%)", template=T, markers=True)
        f2.add_hline(y=30, line_dash='dot', line_color='#94a3b8', annotation_text='Meta 30%')
        f2.update_traces(line_color='#059669')
        f2.update_layout(**BG)
        margen_prom = d2['margen'].mean() if not d2.empty else 0
        if margen_prom >= 30:
            ai2 = asistente_ia('bien', f'Margen promedio saludable ({margen_prom:.1f}%)',
                "El negocio retiene más del 30% de cada venta como utilidad, el estándar sano para food service.",
                ["Mantén el control de costos actual como línea base.",
                 "Usa el margen disponible para invertir en nuevos platillos o marketing."])
        elif margen_prom >= 15:
            ai2 = asistente_ia('mejorar', f'Margen moderado ({margen_prom:.1f}%)',
                "El margen está por debajo de la meta del 30%, en zona de vigilancia.",
                ["Identifica los meses de margen más bajo y revisa qué costo subió ese período.",
                 "Evalúa ajustar el precio de los platillos con menor margen individual."])
        else:
            ai2 = asistente_ia('critico', f'Margen crítico ({margen_prom:.1f}%)',
                "El margen promedio está muy por debajo de lo saludable para el sector.",
                ["Auditoría inmediata de costos de insumos y mermas.",
                 "Sube precios en los platillos con menor margen o retíralos del menú.",
                 "Negocia condiciones de pago y volumen con proveedores clave."])

        # OBJ 12 — Proyección de Utilidad Neta (regresión lineal simple)
        d12 = df_f.groupby('periodo')['utilidad_neta'].sum().reset_index()
        f12 = go.Figure()
        if len(d12) >= 3:
            x = np.arange(len(d12))
            y = d12['utilidad_neta'].values
            m, b = np.polyfit(x, y, 1)
            x_fut = np.arange(len(d12), len(d12) + 3)
            y_fut = m * x_fut + b
            periodos_fut = [f"+{i+1}" for i in range(3)]
            f12.add_trace(go.Scatter(x=d12['periodo'], y=y, name='Histórico', line=dict(color='#2563eb', width=2.5)))
            f12.add_trace(go.Scatter(x=periodos_fut, y=y_fut, name='Proyección', line=dict(color='#7c3aed', width=2.5, dash='dash')))
            tendencia_pos = m > 0
        else:
            f12.add_trace(go.Scatter(x=d12['periodo'], y=d12['utilidad_neta'], name='Histórico'))
            tendencia_pos = True
        f12.update_layout(title="Obj 12 — Proyección de Utilidad Neta (3 períodos)", template=T, **BG)
        if tendencia_pos:
            ai12 = asistente_ia('bien', 'Tendencia proyectada al alza',
                "La regresión lineal sobre la utilidad histórica muestra pendiente positiva.",
                ["Si las condiciones actuales se mantienen, la utilidad debería seguir creciendo.",
                 "Aprovecha para planear expansión de menú o nuevo punto de venta."])
        else:
            ai12 = asistente_ia('mejorar', 'Tendencia proyectada a la baja',
                "La regresión lineal muestra pendiente negativa: sin cambios, la utilidad tiende a caer.",
                ["Actúa antes de que se confirme la caída: revisa precios y costos ya.",
                 "Lanza promociones o nuevos platillos para revertir la tendencia.",
                 "Vuelve a evaluar la proyección el próximo mes con datos frescos."])

        return grid([
            tarjeta(" Obj 1 — Venta Bruta vs Costo de Insumos", 'g1', f1, ai1),
            tarjeta(" Obj 2 — Margen de Utilidad Mensual",      'g2', f2, ai2),
            tarjeta(" Obj 12 — Proyección de Utilidad Neta",    'g12', f12, ai12),
        ])


    if tab == 'rentabilidad':
        # OBJ 4 — Participación de utilidad por categoría
        d4 = df_f.groupby('categoria_platillo')['utilidad_neta'].sum().reset_index()
        f4 = px.pie(d4, names='categoria_platillo', values='utilidad_neta', hole=0.45,
                    title="Obj 4 — Participación de Utilidad por Categoría", template=T,
                    color_discrete_sequence=px.colors.qualitative.Set2)
        f4.update_layout(**BG)
        neg = d4[d4['utilidad_neta'] < 0]
        if not neg.empty:
            ai4 = asistente_ia('critico', f"Categorías con utilidad negativa: {', '.join(neg['categoria_platillo'])}",
                "Una o más categorías restan al resultado global en vez de aportar.",
                ["Revisa el precio de venta de esas categorías frente a su costo real.",
                 "Considera reformular recetas para reducir el costo de insumos.",
                 "Si no mejora en 2 trimestres, evalúa retirarlas del menú."])
        else:
            top = d4.loc[d4['utilidad_neta'].idxmax(), 'categoria_platillo'] if not d4.empty else 'N/A'
            ai4 = asistente_ia('bien', 'Todas las categorías son rentables',
                f"Ninguna categoría tiene utilidad negativa; {top} es la que más aporta.",
                ["El portafolio de menú está sano en su conjunto.",
                 f"Usa el margen de {top} para financiar la prueba de platillos nuevos."])

        # OBJ 6 — Ranking de categorías por utilidad acumulada
        d6 = df_f.groupby('categoria_platillo')['utilidad_neta'].sum().reset_index().sort_values('utilidad_neta')
        f6 = px.bar(d6, x='utilidad_neta', y='categoria_platillo', orientation='h',
                    title="Obj 6 — Ranking de Utilidad por Categoría", template=T,
                    color='utilidad_neta', color_continuous_scale=['#ef4444', '#10b981'])
        f6.update_layout(**BG)
        if not d6.empty:
            peor, mejor = d6.iloc[0], d6.iloc[-1]
            brecha = mejor['utilidad_neta'] - peor['utilidad_neta']
            if peor['utilidad_neta'] >= 0:
                ai6 = asistente_ia('bien', 'Buen desempeño en todo el ranking',
                    f"Incluso la categoría más débil ({peor['categoria_platillo']}) tiene utilidad positiva.",
                    [f"{mejor['categoria_platillo']} lidera y puede ser el eje de una campaña destacada.",
                     "Replica las prácticas de la categoría líder en las demás."])
            else:
                ai6 = asistente_ia('mejorar', f"Brecha amplia entre {mejor['categoria_platillo']} y {peor['categoria_platillo']}",
                    f"La diferencia de utilidad entre la mejor y la peor categoría es de ${brecha:,.0f}.",
                    [f"Investiga por qué {peor['categoria_platillo']} no es rentable: precio, costo o volumen.",
                     f"Aplica al resto del menú las tácticas que hacen exitosa a {mejor['categoria_platillo']}."])
        else:
            ai6 = asistente_ia('mejorar', 'Sin datos suficientes', "No hay categorías para comparar con el filtro actual.", ["Amplía el rango de año o categoría."])

        # OBJ 11 — Eficiencia operativa: Costo/Venta % por categoría
        d11 = df_f.groupby('categoria_platillo')[['costo_insumos', 'venta_bruta']].sum().reset_index()
        d11['ratio'] = np.where(d11['venta_bruta'] > 0, d11['costo_insumos'] / d11['venta_bruta'] * 100, 0)
        f11 = px.bar(d11.sort_values('ratio'), x='categoria_platillo', y='ratio',
                     title="Obj 11 — Eficiencia: % de Costo sobre Venta por Categoría", template=T,
                     color='ratio', color_continuous_scale=['#10b981', '#ef4444'])
        f11.update_layout(**BG)
        peor_efi = d11.loc[d11['ratio'].idxmax()] if not d11.empty else None
        mejor_efi = d11.loc[d11['ratio'].idxmin()] if not d11.empty else None
        if peor_efi is not None and peor_efi['ratio'] > 45:
            ai11 = asistente_ia('mejorar', f"{peor_efi['categoria_platillo']} consume {peor_efi['ratio']:.1f}% de su venta en costos",
                "Ese porcentaje está por encima del umbral saludable (45%) para el sector de alimentos.",
                [f"Busca proveedores alternativos de insumos para {peor_efi['categoria_platillo']}.",
                 "Revisa el tamaño de porción o receta para optimizar costo sin perder calidad.",
                 "Considera ajustar el precio de venta si el costo no puede bajar más."])
        else:
            ai11 = asistente_ia('bien', f"{mejor_efi['categoria_platillo'] if mejor_efi is not None else 'El menú'} es la categoría más eficiente",
                "Todas las categorías se mantienen dentro de un porcentaje de costo saludable sobre su venta.",
                ["El costeo de recetas está bien calibrado.",
                 "Usa la categoría más eficiente como modelo para ajustar el resto del menú."])

        return grid([
            tarjeta(" Obj 4 — Participación de Utilidad por Categoría", 'g4', f4, ai4),
            tarjeta(" Obj 6 — Ranking de Utilidad por Categoría",       'g6', f6, ai6),
            tarjeta(" Obj 11 — Eficiencia Costo/Venta por Categoría",   'g11', f11, ai11),
        ])

    if tab == 'operacion':
        # OBJ 3 — Ticket promedio por platillo vendido
        d3 = df_f.groupby('periodo')[['venta_bruta', 'platillos_vendidos']].sum().reset_index()
        d3['ticket'] = np.where(d3['platillos_vendidos'] > 0, d3['venta_bruta'] / d3['platillos_vendidos'], 0)
        f3 = px.line(d3, x='periodo', y='ticket', title="Obj 3 — Ticket Promedio por Platillo Vendido", template=T, markers=True)
        f3.update_traces(line_color='#d97706')
        f3.update_layout(**BG)
        if len(d3) >= 2 and d3['ticket'].iloc[0] > 0:
            var_ticket = (d3['ticket'].iloc[-1] / d3['ticket'].iloc[0] - 1) * 100
        else:
            var_ticket = 0
        if var_ticket >= 0:
            ai3 = asistente_ia('bien', f'El ticket promedio aumentó {var_ticket:.1f}%',
                "Los clientes están gastando más por platillo, sea por mezcla de venta o mejores precios.",
                ["Sigue promoviendo combos o platillos de mayor valor.",
                 "Documenta qué estrategia de venta cruzada funcionó mejor este período."])
        else:
            ai3 = asistente_ia('mejorar', f'El ticket promedio cayó {abs(var_ticket):.1f}%',
                "El gasto promedio por platillo está bajando frente al período inicial.",
                ["Impulsa venta sugestiva (upselling) de bebidas o postres al momento de ordenar.",
                 "Revisa si hay descuentos excesivos que estén erosionando el ticket."])

        # OBJ 8 — Costo unitario promedio por categoría
        d8 = df_f.groupby('categoria_platillo')[['costo_insumos', 'platillos_vendidos']].sum().reset_index()
        d8['costo_unit'] = np.where(d8['platillos_vendidos'] > 0, d8['costo_insumos'] / d8['platillos_vendidos'], 0)
        f8 = px.bar(d8.sort_values('costo_unit'), x='categoria_platillo', y='costo_unit',
                    title="Obj 8 — Costo Unitario Promedio por Categoría", template=T,
                    color_discrete_sequence=['#f59e0b'])
        f8.update_layout(**BG)
        if not d8.empty:
            disp = d8['costo_unit'].std() / d8['costo_unit'].mean() if d8['costo_unit'].mean() > 0 else 0
            if disp < 0.4:
                ai8 = asistente_ia('bien', 'Costos unitarios homogéneos entre categorías',
                    "La variación de costo por unidad entre categorías es baja y predecible.",
                    ["Facilita presupuestar compras de insumos con precisión.",
                     "Mantén el estándar de recetas actual."])
            else:
                ai8 = asistente_ia('mejorar', 'Costos unitarios muy dispares entre categorías',
                    "Hay categorías con costo por unidad mucho más alto que otras, lo que complica el control de compras.",
                    ["Estandariza porciones y recetas en las categorías más costosas.",
                     "Negocia insumos por separado para las categorías de mayor costo unitario."])
        else:
            ai8 = asistente_ia('mejorar', 'Sin datos suficientes', "No hay categorías para este filtro.", ["Amplía el rango de año o categoría."])

        # OBJ 10 — Comparativo trimestral de utilidad neta
        d10 = df_f.groupby(['anio', 'trimestre'])['utilidad_neta'].sum().reset_index()
        d10['anio'] = d10['anio'].astype(str)
        f10 = px.bar(d10, x='trimestre', y='utilidad_neta', color='anio', barmode='group',
                     title="Obj 10 — Utilidad Neta por Trimestre", template=T,
                     labels={'trimestre': 'Trimestre', 'utilidad_neta': 'Utilidad ($)'})
        f10.update_layout(**BG)
        d10_tot = d10.groupby('trimestre')['utilidad_neta'].sum()
        if not d10_tot.empty:
            peor_tri = d10_tot.idxmin()
            if d10_tot.min() >= 0:
                ai10 = asistente_ia('bien', 'Utilidad positiva en los 4 trimestres',
                    f"Incluso el trimestre más débil (Q{peor_tri}) cierra en positivo.",
                    ["El negocio no depende de un solo trimestre para ser rentable.",
                     f"Refuerza Q{peor_tri} con promociones puntuales para parejar el año."])
            else:
                ai10 = asistente_ia('mejorar', f'Q{peor_tri} cierra con pérdidas',
                    f"El trimestre {peor_tri} concentra el peor resultado del año.",
                    [f"Investiga qué pasó operativamente en Q{peor_tri}: estacionalidad, costos o menor tráfico.",
                     "Diseña una promoción o menú especial para ese trimestre el próximo año."])
        else:
            ai10 = asistente_ia('mejorar', 'Sin datos suficientes', "No hay trimestres para comparar con este filtro.", ["Amplía el rango de año."])

        return grid([
            tarjeta(" Obj 3 — Ticket Promedio por Platillo",        'g3', f3, ai3),
            tarjeta(" Obj 8 — Costo Unitario Promedio por Categoría", 'g8', f8, ai8),
            tarjeta(" Obj 10 — Utilidad Neta por Trimestre",         'g10', f10, ai10),
        ])


    if tab == 'riesgo':
        # OBJ 5 — Crecimiento interanual de ventas (YoY %)
        d5 = df_f.groupby('anio')['venta_bruta'].sum().reset_index().sort_values('anio')
        d5['yoy'] = d5['venta_bruta'].pct_change() * 100
        f5 = px.bar(d5.dropna(subset=['yoy']), x='anio', y='yoy', title="Obj 5 — Crecimiento Interanual de Venta Bruta (%)",
                    template=T, color='yoy', color_continuous_scale=['#ef4444', '#10b981'])
        f5.update_layout(**BG)
        ultimo_yoy = d5['yoy'].dropna().iloc[-1] if d5['yoy'].dropna().shape[0] > 0 else None
        if ultimo_yoy is None:
            ai5 = asistente_ia('mejorar', 'Sin suficiente histórico', "Se necesitan al menos 2 años de datos para calcular crecimiento interanual.", ["Amplía el filtro de año."])
        elif ultimo_yoy >= 0:
            ai5 = asistente_ia('bien', f'Crecimiento interanual positivo ({ultimo_yoy:.1f}%)',
                "El último año registrado vendió más que el anterior.",
                ["Identifica qué acción comercial impulsó el crecimiento y repítela.",
                 "Fija una meta de crecimiento similar o mayor para el siguiente año."])
        else:
            ai5 = asistente_ia('mejorar', f'Caída interanual ({ultimo_yoy:.1f}%)',
                "El último año registrado vendió menos que el anterior.",
                ["Revisa si hubo pérdida de clientes frecuentes o menor tráfico.",
                 "Lanza una campaña de reactivación de clientes inactivos."])

        # OBJ 7 — Estacionalidad: heatmap mes x año de venta bruta
        d7 = df_f.pivot_table(index='anio', columns='mes', values='venta_bruta', aggfunc='sum').fillna(0)
        f7 = px.imshow(d7, title="Obj 7 — Estacionalidad: Venta Bruta por Mes y Año", template=T,
                       color_continuous_scale='Blues', labels=dict(x='Mes', y='Año', color='Venta ($)'), aspect='auto')
        f7.update_layout(**BG)
        prom_mes = df_f.groupby('mes')['venta_bruta'].sum()
        cv_estacional = (prom_mes.std() / prom_mes.mean()) if prom_mes.mean() > 0 else 0
        if cv_estacional < 0.3:
            ai7 = asistente_ia('bien', 'Estacionalidad baja: ventas parejas todo el año',
                f"El coeficiente de variación mensual es {cv_estacional:.2f}, lo que indica poca dependencia de temporada.",
                ["El negocio no depende de meses pico para sostenerse.",
                 "Mantén el ritmo de operación actual durante todo el año."])
        else:
            mes_bajo = int(prom_mes.idxmin())
            ai7 = asistente_ia('mejorar', 'Estacionalidad marcada detectada',
                f"El coeficiente de variación mensual es {cv_estacional:.2f}: hay meses claramente más débiles (ej. mes {mes_bajo}).",
                [f"Diseña una promoción específica para reactivar el mes {mes_bajo}.",
                 "Diversifica el menú con opciones de temporada para suavizar la caída."])

        # OBJ 9 — Volatilidad de la utilidad mensual (riesgo)
        d9 = df_f.groupby(['anio', 'mes'])['utilidad_neta'].sum().reset_index()
        d9_anio = d9.groupby('anio')['utilidad_neta'].std().reset_index().rename(columns={'utilidad_neta': 'volatilidad'})
        d9_anio['anio'] = d9_anio['anio'].astype(str)
        f9 = px.bar(d9_anio, x='anio', y='volatilidad', title="Obj 9 — Volatilidad Mensual de la Utilidad por Año",
                    template=T, color_discrete_sequence=['#7c3aed'])
        f9.update_layout(**BG)
        media_ut = d9['utilidad_neta'].mean()
        cv_ut = (d9['utilidad_neta'].std() / media_ut) if media_ut else 0
        if abs(cv_ut) < 0.5:
            ai9 = asistente_ia('bien', 'Utilidad mensual estable',
                f"La variabilidad de la utilidad mes a mes es baja (CV={cv_ut:.2f}).",
                ["Un flujo de utilidad predecible facilita planear inversión y nómina.",
                 "Mantén el control de costos que sostiene esta estabilidad."])
        else:
            ai9 = asistente_ia('mejorar', 'Utilidad mensual muy volátil',
                f"La variabilidad de la utilidad mes a mes es alta (CV={cv_ut:.2f}), lo que dificulta planear con certeza.",
                ["Identifica los meses atípicos y qué costo o evento los causó.",
                 "Crea un fondo de reserva para los meses de utilidad más baja.",
                 "Estandariza precios y promociones para reducir picos y valles."])

        return grid([
            tarjeta(" Obj 5 — Crecimiento Interanual de Venta Bruta", 'g5', f5, ai5),
            tarjeta(" Obj 7 — Estacionalidad Mes x Año",              'g7', f7, ai7),
            tarjeta(" Obj 9 — Volatilidad Mensual de la Utilidad",    'g9', f9, ai9),
        ])

    return html.Div()


if __name__ == '__main__':
    Timer(1, lambda: webbrowser.open_new("http://127.0.0.1:5000/")).start()
    app.run(debug=False, port=5000)
    