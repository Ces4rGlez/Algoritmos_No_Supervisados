from flask import Flask, render_template, request, jsonify, send_file, make_response
import pandas as pd
import numpy as np
import os
from ml_models import MBTIClusterModel
import io
import datetime
import json
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa

# ─── Configuración inicial de la aplicación Flask ───────────────────────────
app = Flask(__name__)
app.config['MODEL_DIR'] = 'models'         # Carpeta donde se guardan los modelos .pkl
app.config['UPLOAD_FOLDER'] = 'uploads'    # Carpeta donde se guarda el dataset subido por el usuario

# Crear las carpetas necesarias si aún no existen
for folder in [app.config['MODEL_DIR'], app.config['UPLOAD_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Limpiar la carpeta de uploads cada vez que el servidor arranca.
# Esto garantiza que el usuario siempre empiece desde cero y elija su propio dataset.
for filename in os.listdir(app.config['UPLOAD_FOLDER']):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        if os.path.isfile(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f"Error al limpiar la carpeta de uploads: {e}")

# Carpeta donde se puede colocar un dataset interno por defecto
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_data():
    """
    Función auxiliar que busca y carga el dataset activo en memoria.
    Primero busca un archivo Excel (.xlsx), si no existe busca un CSV.
    Retorna un DataFrame vacío si no hay ningún archivo subido.
    """
    csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.csv')
    xlsx_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.xlsx')
    
    if os.path.exists(xlsx_path):
        try:
            return pd.read_excel(xlsx_path)
        except:
            pass
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except:
            pass
            
    return pd.DataFrame()

def apply_dynamic_filters(df, args):
    """
    Aplica los filtros que el usuario seleccionó en la interfaz.
    Filtra el DataFrame por columnas de texto (categorías). Si el valor es 'Todos', no filtra.
    """
    if df.empty:
        return df
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    for col in categorical_cols:
        val = args.get(col)
        if val and val != 'Todos' and col in df.columns:
            df = df[df[col] == val]
    return df

@app.route('/')
def index():
    """
    Ruta principal. Renderiza y devuelve la página HTML (index.html) al navegador del usuario.
    """
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """
    Recibe un archivo (CSV o Excel) subido por el usuario desde la web.
    Borra cualquier dataset anterior y guarda el nuevo en la carpeta 'uploads/'.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        # Borrar el dataset anterior para no acumular archivos
        for old in ['uploaded_dataset.csv', 'uploaded_dataset.xlsx']:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], old)
            if os.path.exists(old_path):
                os.remove(old_path)
                
        ext = '.csv' if file.filename.endswith('.csv') else '.xlsx'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_dataset{ext}')
        file.save(filepath)
        return jsonify({'message': '¡Archivo subido exitosamente!'})
    else:
        return jsonify({'error': 'Formato inválido. Solo se permiten archivos CSV o XLSX.'}), 400

@app.route('/api/load_internal', methods=['POST'])
def api_load_internal():
    """
    Carga el dataset 'dataset_interno.csv' por defecto (el de 10,000 registros).
    Lo copia a la carpeta de 'uploads/' para que la aplicación lo use como base de datos activa.
    """
    internal_file = os.path.join('data', 'dataset_interno.csv')
    if not os.path.exists(internal_file):
        return jsonify({'error': 'No se encontró dataset_interno.csv en la carpeta data/'}), 404
        
    try:
        import shutil
        # Copiar el dataset interno a la carpeta de uploads para activarlo
        dest = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.csv')
        shutil.copy(internal_file, dest)
        
        # Borrar cualquier Excel que haya quedado rezagado de una sesión anterior
        xlsx_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.xlsx')
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)
            
        return jsonify({'message': 'Dataset interno cargado exitosamente.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def api_data():
    """
    Sirve para mandar los datos del dataset en formato tabla (paginado) hacia la página web.
    También aplica filtros dinámicos si el usuario selecciona algo en la interfaz.
    """
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data found'}), 404
        
    df = apply_dynamic_filters(df, request.args)
        
    # Paginación: se mandan los datos en bloques (páginas) para no saturar el navegador
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    total_records = len(df)
    
    start = (page - 1) * per_page
    end = start + per_page
    
    # Reemplazar valores vacíos (NaN) para que la respuesta JSON no tenga errores
    df = df.fillna('')
    data = df.iloc[start:end].to_dict(orient='records')
    columns = list(df.columns)
    
    # Separar columnas numéricas (para el modelo) y categóricas (para los filtros)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Recopilar los valores únicos de cada columna categórica para generar los desplegables del filtro
    filters_info = {}
    for col in categorical_cols:
        if 2 <= df[col].nunique() <= 20:
            filters_info[col] = df[col].dropna().unique().tolist()
    
    return jsonify({
        'data': data,
        'columns': columns,
        'numeric_columns': numeric_cols,
        'filters_info': filters_info,
        'total': total_records,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """
    Calcula y devuelve todas las estadísticas descriptivas del dataset activo:
    distribuciones, histogramas, media, mediana, desviación estándar, etc.
    También genera interpretaciones automáticas en texto.
    """
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data found'}), 404
        
    df = apply_dynamic_filters(df, request.args)
        
    if df.empty:
        return jsonify({
            'total_records': 0,
            'cat_dist': {},
            'desc_stats': {},
            'hist_data': {},
            'hist_col': None,
            'numeric_cols': [],
            'interpretations': []
        })
        
    stats = {
        'total_records': len(df),
        'cat_dist': {},       # Distribución de columnas categóricas (para gráficas de pastel)
        'desc_stats': {},     # Estadísticas descriptivas por columna numérica
        'hist_data': {},
        'hist_col': None,
        'numeric_cols': [],
        'interpretations': [] # Interpretaciones automáticas en texto
    }
    
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Conteo de frecuencias para las gráficas de pastel de datos categóricos
    for col in categorical_cols:
        if 2 <= df[col].nunique() <= 20:
            stats['cat_dist'][col] = df[col].value_counts().to_dict()
                
    # Estadísticas descriptivas para cada columna numérica
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    stats['numeric_cols'] = numeric_cols
    
    for c in numeric_cols:
        s = df[c].dropna()
        if len(s) == 0: continue
        
        c_min = float(s.min())
        c_max = float(s.max())
        c_mean = float(s.mean())
        c_std = float(s.std()) if len(s) > 1 else 0.0
        
        stats['desc_stats'][c] = {
            'min': c_min,
            'max': c_max,
            'range': c_max - c_min,    # Rango (diferencia entre max y min)
            'mean': c_mean,            # Promedio aritmético
            'median': float(s.median()),
            'std': c_std,              # Desviación estándar (qué tan dispersos están los datos)
            'var': float(s.var()) if len(s) > 1 else 0.0,       # Varianza
            'skew': float(s.skew()) if len(s) > 2 else 0.0,     # Sesgo (asimetría de la distribución)
            'kurtosis': float(s.kurtosis()) if len(s) > 3 else 0.0  # Curtosis (altura del pico)
        }
        
        # Reglas simples para generar interpretaciones automáticas en texto
        skew = stats['desc_stats'][c]['skew']
        if skew > 1:
            stats['interpretations'].append(f"La variable '{c}' tiene una asimetría positiva alta (sesgada a la derecha).")
        elif skew < -1:
            stats['interpretations'].append(f"La variable '{c}' tiene una asimetría negativa alta (sesgada a la izquierda).")
            
        if c_std > c_mean and c_mean > 0:
            stats['interpretations'].append(f"La variable '{c}' presenta una alta dispersión (Desviación Estándar mayor que la Media).")
            
    # Datos de histograma para TODAS las columnas numéricas (15 intervalos cada una)
    stats['hist_data_all'] = {}
    for col in numeric_cols:
        s_hist = df[col].dropna()
        if len(s_hist) > 0:
            hist, bin_edges = np.histogram(s_hist, bins=15)
            stats['hist_data_all'][col] = {
                'counts': hist.tolist(),    # Frecuencia (cuántos datos hay en cada intervalo)
                'bins': bin_edges.tolist()  # Los límites de cada intervalo del histograma
            }
            
    if not stats['interpretations']:
        stats['interpretations'].append("Las variables numéricas muestran una distribución relativamente normal y simétrica.")
            
    return jsonify(stats)

@app.route('/api/report/pdf', methods=['GET'])
def api_report_pdf():
    """
    Genera y descarga un reporte estadístico en formato PDF del dataset actual.
    Usa la librería xhtml2pdf para convertir el template HTML a PDF.
    """
    df = get_data()
    if df.empty:
        return "No hay datos disponibles", 404
        
    df = apply_dynamic_filters(df, request.args)
    
    # Calcular estadísticas para incluir en el reporte
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    desc_stats = {}
    for c in numeric_cols:
        s = df[c].dropna()
        if len(s) == 0: continue
        desc_stats[c] = {
            'min': round(float(s.min()), 2),
            'max': round(float(s.max()), 2),
            'mean': round(float(s.mean()), 2),
            'median': round(float(s.median()), 2),
            'std': round(float(s.std()), 2),
            'skew': round(float(s.skew()), 2) if len(s) > 2 else 0.0
        }
        
    html = render_template('report.html', 
                           total_records=len(df),
                           desc_stats=desc_stats,
                           numeric_cols=numeric_cols,
                           date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                           
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("utf-8")), result)
    if not pdf.err:
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=reporte_estadistico.pdf'
        return response
    else:
        return "Error al generar el PDF", 500

@app.route('/api/train', methods=['POST'])
def api_train():
    """
    Ruta principal del entrenamiento. Recibe la configuración del usuario
    (algoritmo, número de clusters, columnas a usar) y entrena el modelo K-Means.
    Devuelve las coordenadas PCA para la gráfica, el Silhouette Score, composición
    de clusters y una descripción heurística de cada grupo.
    """
    data = request.json
    algorithm = data.get('algorithm', 'kmeans')
    n_clusters = int(data.get('n_clusters', 16))
    features = data.get('features', [])     # Columnas numéricas seleccionadas por el usuario
    
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No hay datos para entrenar. Sube un dataset primero.'}), 404
        
    if not features:
        # Si el usuario no seleccionó columnas, usar todas las numéricas por defecto
        features = df.select_dtypes(include=[np.number]).columns.tolist()
            
    for f in features:
        if f not in df.columns:
            return jsonify({'error': f'La columna {f} no se encontró en el dataset.'}), 400
            
    model = MBTIClusterModel()
    try:
        # Rellenar valores vacíos con el promedio de cada columna antes de entrenar
        df_ml = df[features].fillna(df[features].mean())
        results = model.train(df_ml, features, algorithm=algorithm, n_clusters=n_clusters)
        
        # Guardar el modelo y los resultados en la memoria del servidor para uso posterior
        app.config['CURRENT_MODEL'] = model
        app.config['LAST_LABELS'] = results['labels']
        app.config['LAST_FEATURES'] = features
        
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        eval_col = None
        
        # Prioridad 1: Buscar la columna de tipo de personalidad MBTI
        priority_names = ['tipo_resultante', 'tipo_mbti', 'personalidad', 'mbti']
        for p in priority_names:
            if p in categorical_cols:
                eval_col = p
                break
                
        # Prioridad 2: Si no existe, usar cualquier columna de texto con entre 2 y 50 categorías
        if not eval_col and len(categorical_cols) > 0:
            for col in categorical_cols:
                if 2 <= df[col].nunique() <= 50:
                    eval_col = col
                    break
                    
        if eval_col:
            # ────────────────────────────────────────────────────────────────
            # CÁLCULO DE PUREZA (EFECTIVIDAD DEL CLÚSTER)
            # ────────────────────────────────────────────────────────────────
            # ¿Qué es la pureza?
            # Es una métrica que mide qué tan "homogéneo" (efectivo) es un clúster.
            # Si el 90% de las personas de un clúster tienen el mismo tipo MBTI,
            # la pureza es 90% -> el clúster es muy efectivo y bien definido.
            # Si cada persona tiene un tipo diferente, la pureza será baja -> el grupo es difuso.
            #
            # Fórmula de pureza por clúster:
            #   Pureza(k) = (cantidad de personas con el tipo dominante en el clúster k)
            #               / (total de personas en el clúster k) * 100
            #
            # Un clúster con 80%+ de pureza indica que K-Means logró agrupar perfiles
            # MBTI similares sin haberlos visto nunca (aprendizaje no supervisado).
            # ────────────────────────────────────────────────────────────────
            composition = []
            # Agregar la columna de etiquetas de clúster al DataFrame para poder filtrar por grupo
            df_with_labels = df.copy()
            df_with_labels['cluster'] = results['labels']
            
            for cluster_id in range(n_clusters):
                # Filtrar solo a las personas que pertenecen a este clúster
                cluster_data = df_with_labels[df_with_labels['cluster'] == cluster_id]
                if len(cluster_data) > 0:
                    # value_counts(normalize=True) calcula la proporción de cada tipo en el grupo
                    # por ejemplo: {'INTJ': 0.72, 'INTP': 0.15, 'INFJ': 0.13}
                    dist = cluster_data[eval_col].value_counts(normalize=True)
                    top_label = dist.index[0]      # El tipo MBTI más frecuente en este clúster
                    purity = dist.iloc[0] * 100    # % de personas del clúster que tienen ese tipo
                    
                    composition.append({
                        'cluster': cluster_id,
                        'size': len(cluster_data),       # Cuántas personas hay en este clúster
                        'dominant_label': top_label,     # El tipo de personalidad dominante
                        'purity': round(purity, 2),      # % de efectividad del clúster
                        'eval_col': eval_col             # La columna usada para evaluar (ej. 'tipo_resultante')
                    })
            results['composition'] = composition

        # ────────────────────────────────────────────────────────────────
        # DESCRIPCIÓN HEURÍSTICA DE CADA CLÚSTER
        # ────────────────────────────────────────────────────────────────
        # Genera automáticamente una oración en texto que describe el perfil de cada clúster.
        # Lo hace comparando el promedio del clúster contra el promedio global del dataset.
        # Si una dimensión del clúster está más del 15% por encima o debajo del promedio global,
        # se considera una característica "destacada" y se incluye en la descripción.
        # ────────────────────────────────────────────────────────────────
        cluster_descriptions = {}
        cluster_stats = {}
        df_ml_labels = df_ml.copy()
        df_ml_labels['cluster'] = results['labels']
        
        for c_id in range(n_clusters):
            c_data = df_ml_labels[df_ml_labels['cluster'] == c_id][features]
            if len(c_data) > 0:
                means = c_data.mean()                  # Promedio de este clúster
                overall_means = df_ml[features].mean() # Promedio global de todo el dataset
                
                cluster_stats[f"Clúster {c_id}"] = means.to_dict()
                
                desc = []
                deviations = []
                for f in features:
                    if overall_means[f] != 0:
                        # Fórmula: desviación relativa = (promedio_clúster - promedio_global) / promedio_global * 100
                        # Un resultado de +20% significa que este clúster tiene un 20% más que el promedio en esa variable
                        pct_diff = ((means[f] - overall_means[f]) / overall_means[f]) * 100
                        deviations.append((f, pct_diff))
                
                # Ordenar de mayor a menor desviación para destacar las más importantes primero
                deviations.sort(key=lambda x: abs(x[1]), reverse=True)
                
                altos = []
                bajos = []
                
                for f, pct in deviations:
                    if pct > 15:
                        altos.append(f"{f} (+{pct:.1f}%)")
                    elif pct < -15:
                        bajos.append(f"{f} ({pct:.1f}%)")
                        
                if altos and bajos:
                    desc_text = f"Perfil fuertemente definido por picos en {', '.join(altos)}; mientras que carece de {', '.join(bajos)}."
                elif altos:
                    desc_text = f"Grupo caracterizado exclusivamente por dominio superior al promedio en {', '.join(altos)}."
                elif bajos:
                    desc_text = f"Clúster que se agrupa por tener déficit o niveles muy inferiores en {', '.join(bajos)}."
                else:
                    desc_text = "Perfil neutro o muy cercano al promedio global de la población. No destaca por extremos."
                
                cluster_descriptions[f"Clúster {c_id}"] = desc_text
            else:
                cluster_descriptions[f"Clúster {c_id}"] = "Clúster vacío sin datos representativos."
                cluster_stats[f"Clúster {c_id}"] = {f: 0 for f in features}

        # Limitar a 2000 puntos en la gráfica para no saturar el navegador
        if len(results['x_pca']) > 2000:
            indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
            results['x_pca'] = [results['x_pca'][i] for i in indices]
            results['y_pca'] = [results['y_pca'][i] for i in indices]
            results['labels'] = [results['labels'][i] for i in indices]

        results['message'] = 'Modelo entrenado exitosamente.'
        results['algorithm'] = algorithm
        results['n_clusters'] = n_clusters
        results['features'] = features
        results['silhouette_score'] = results.get('silhouette', None)
        results['cluster_descriptions'] = cluster_descriptions
        results['cluster_stats'] = cluster_stats
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incremental_train', methods=['POST'])
def api_incremental_train():
    """
    Ruta para aplicar aprendizaje incremental (fine-tuning) sobre el modelo
    actualmente cargado usando el dataset activo.
    """
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No hay datos para entrenar. Sube un dataset primero.'}), 404
        
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No hay ningún modelo cargado para actualizar. Carga un modelo KMeans primero.'}), 400
        
    model = app.config['CURRENT_MODEL']
    
    if getattr(model, 'model_type', '') != 'kmeans':
        return jsonify({'error': 'El aprendizaje incremental solo está soportado para modelos KMeans.'}), 400
        
    # Verificar que el dataset actual tenga las mismas columnas con las que se entrenó el modelo original
    missing = [f for f in model.features if f not in df.columns]
    if missing:
        return jsonify({'error': f'El dataset actual no tiene las columnas necesarias para actualizar este modelo: {missing}'}), 400
        
    try:
        df_ml = df[model.features].fillna(df[model.features].mean())
        results = model.incremental_train(df_ml)
        
        # Guardar en la configuración de la app
        app.config['LAST_LABELS'] = results['labels']
        app.config['LAST_FEATURES'] = model.features
        
        # Generar descripción heurística (reutilizando la lógica normal)
        cluster_descriptions = {}
        cluster_stats = {}
        df_ml_labels = df_ml.copy()
        df_ml_labels['cluster'] = results['labels']
        
        for c_id in range(model.n_clusters):
            c_data = df_ml_labels[df_ml_labels['cluster'] == c_id][model.features]
            if len(c_data) > 0:
                means = c_data.mean()
                overall_means = df_ml[model.features].mean()
                cluster_stats[f"Clúster {c_id}"] = means.to_dict()
                deviations = []
                for f in model.features:
                    if overall_means[f] != 0:
                        pct_diff = ((means[f] - overall_means[f]) / overall_means[f]) * 100
                        deviations.append((f, pct_diff))
                deviations.sort(key=lambda x: abs(x[1]), reverse=True)
                
                altos = [f"{f} (+{pct:.1f}%)" for f, pct in deviations if pct > 15]
                bajos = [f"{f} ({pct:.1f}%)" for f, pct in deviations if pct < -15]
                if altos and bajos:
                    cluster_descriptions[f"Clúster {c_id}"] = f"Perfil con picos en {', '.join(altos)}; y déficit en {', '.join(bajos)}."
                elif altos:
                    cluster_descriptions[f"Clúster {c_id}"] = f"Destaca superior al promedio en {', '.join(altos)}."
                elif bajos:
                    cluster_descriptions[f"Clúster {c_id}"] = f"Déficit en {', '.join(bajos)}."
                else:
                    cluster_descriptions[f"Clúster {c_id}"] = "Perfil muy cercano al promedio global."
            else:
                cluster_descriptions[f"Clúster {c_id}"] = "Clúster vacío."
                cluster_stats[f"Clúster {c_id}"] = {f: 0 for f in model.features}
                
        # Limitar a 2000 puntos para la gráfica
        if len(results['x_pca']) > 2000:
            indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
            results['x_pca'] = [results['x_pca'][i] for i in indices]
            results['y_pca'] = [results['y_pca'][i] for i in indices]
            results['labels'] = [results['labels'][i] for i in indices]
            
        results['message'] = 'Modelo actualizado exitosamente mediante aprendizaje incremental.'
        results['features'] = model.features
        results['silhouette_score'] = results.get('silhouette', None)
        results['cluster_descriptions'] = cluster_descriptions
        results['cluster_stats'] = cluster_stats
        
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/find_optimal_k', methods=['POST'])
def api_optimal_k():
    data = request.json
    algorithm = data.get('algorithm', 'kmeans')
    features = data.get('features', [])
    max_k = int(data.get('max_k', 20))
    
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data to evaluate'}), 404
        
    if not features:
        features = df.select_dtypes(include=[np.number]).columns.tolist()
            
    for f in features:
        if f not in df.columns:
            return jsonify({'error': f'Feature {f} not found in dataset'}), 400
            
    model = MBTIClusterModel()
    try:
        df_ml = df[features].fillna(df[features].mean())
        results = model.calculate_optimal_k(df_ml, features, algorithm=algorithm, max_k=max_k)
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def api_history():
    """
    Devuelve el historial de todos los modelos que alguna vez se guardaron.
    Lee los archivos .meta.json de la carpeta 'models/' para obtener los metadatos
    sin tener que cargar los pesados archivos .pkl.
    """
    models_dir = app.config['MODEL_DIR']
    history = []
    
    if os.path.exists(models_dir):
        for f in os.listdir(models_dir):
            if f.endswith('.meta.json'):
                try:
                    with open(os.path.join(models_dir, f), 'r') as file:
                        meta = json.load(file)
                        history.append(meta)
                except:
                    pass
                    
    # Ordenar del más reciente al más antiguo
    history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({'history': history})

@app.route('/api/save_model', methods=['POST'])
def api_save_model():
    """
    Guarda el modelo actualmente entrenado en disco como archivo .pkl.
    También permite al usuario agregarle una descripción personalizada.
    """
    data = request.json
    description = data.get('description', '')
    
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No hay ningún modelo entrenado para guardar.'}), 400
        
    model = app.config['CURRENT_MODEL']
    # Generar un nombre único con el algoritmo y la fecha/hora actual
    filename = f"model_{model.model_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    
    try:
        saved_path = model.save(filepath, description)
        return jsonify({'message': 'Modelo guardado exitosamente.', 'path': saved_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_model', methods=['POST'])
def api_load_model():
    """
    Carga un modelo .pkl guardado y lo deja listo para usar.
    Luego aplica ese modelo al dataset actual para generar las gráficas sin necesidad de reentrenar.
    """
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': 'No se proporcionó el nombre del archivo.'}), 400

    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': f'Archivo de modelo no encontrado: {filename}'}), 404

    model = MBTIClusterModel()
    try:
        metadata = model.load(filepath)
    except Exception as e:
        return jsonify({'error': f'Error al cargar el modelo: {str(e)}'}), 500

    app.config['CURRENT_MODEL'] = model

    df = get_data()
    if df.empty or not model.features:
        return jsonify({
            'message': 'Modelo cargado (sin dataset activo para graficar)',
            'metadata': metadata,
            'features': model.features
        })

    # Verificar que el dataset actual tenga las mismas columnas con las que se entrenó
    missing = [f for f in model.features if f not in df.columns]
    if missing:
        return jsonify({
            'error': f'El modelo requiere columnas que no existen en el dataset actual: {missing}'
        }), 400

    # Aplicar el modelo cargado al dataset para generar las coordenadas PCA de la gráfica
    df_ml = df[model.features].fillna(df[model.features].mean())
    X_pca = model.pca.transform(df_ml)             # Reducir dimensiones con el PCA guardado
    labels = model.model.predict(df_ml).tolist()   # Clasificar a cada persona en un clúster
    n_comp = X_pca.shape[1]

    app.config['LAST_LABELS'] = labels
    app.config['LAST_FEATURES'] = model.features

    results = {
        'labels': labels,
        'x_pca': X_pca[:, 0].tolist(),
        'y_pca': X_pca[:, 1].tolist() if n_comp > 1 else [0]*len(labels),
        'z_pca': X_pca[:, 2].tolist() if n_comp > 2 else [0]*len(labels),
        'explained_variance': float(sum(model.pca.explained_variance_ratio_)),
        'n_clusters': len(set(labels)),
        'algorithm': model.model_type,
        'features': model.features,
        'metadata': metadata
    }
    
    # Calcular la composición de clústeres (pureza de tipos MBTI) con el modelo cargado
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    eval_col = None
    priority_names = ['tipo_resultante', 'tipo_mbti', 'personalidad', 'mbti']
    for p in priority_names:
        if p in categorical_cols:
            eval_col = p
            break
            
    if not eval_col and len(categorical_cols) > 0:
        for col in categorical_cols:
            if 2 <= df[col].nunique() <= 50:
                eval_col = col
                break
                
    if eval_col:
        composition = []
        df_with_labels = df.copy()
        df_with_labels['cluster'] = labels
        unique_clusters = set(labels)
        
        for cluster_id in unique_clusters:
            cluster_data = df_with_labels[df_with_labels['cluster'] == cluster_id]
            if len(cluster_data) > 0:
                dist = cluster_data[eval_col].value_counts(normalize=True)
                top_label = dist.index[0]
                purity = dist.iloc[0] * 100
                
                composition.append({
                    'cluster': cluster_id,
                    'size': len(cluster_data),
                    'dominant_label': top_label,
                    'purity': round(purity, 2),
                    'eval_col': eval_col
                })
        composition.sort(key=lambda x: x['cluster'])
        results['composition'] = composition
    
    # Limitar a 2000 puntos en la gráfica para no saturar el navegador
    if len(results['x_pca']) > 2000:
        indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
        results['x_pca']  = [results['x_pca'][i]  for i in indices]
        results['y_pca']  = [results['y_pca'][i]  for i in indices]
        results['labels'] = [results['labels'][i]  for i in indices]

    return jsonify(results)

@app.route('/api/list_models', methods=['GET'])
def api_list_models():
    """
    Lista todos los modelos .pkl guardados en la carpeta 'models/'.
    Lee los metadatos (.meta.json) de cada uno para mostrarlos en el selector de la UI.
    """
    model_dir = app.config['MODEL_DIR']
    files = []
    for f in os.listdir(model_dir):
        if f.endswith('.pkl'):
            meta_path = os.path.join(model_dir, f + '.meta.json')
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path) as mf:
                    meta = json.load(mf)
            files.append({'filename': f, 'metadata': meta})
    # Ordenar de más reciente a más antiguo
    files.sort(key=lambda x: x['filename'], reverse=True)
    return jsonify(files)

@app.route('/api/download_results', methods=['GET'])
def api_download_results():
    """
    Descarga el dataset original pero con una columna extra 'cluster' que indica
    a qué grupo pertenece cada persona según el último entrenamiento.
    Disponible en formato CSV o Excel.
    """
    if 'LAST_LABELS' not in app.config:
        return jsonify({'error': 'No hay resultados de clustering disponibles.'}), 400

    df = get_data()
    labels = app.config['LAST_LABELS']

    if len(labels) != len(df):
        # Si el dataset tiene más filas que etiquetas (ej. por muestreo), rellenar con None
        df_out = df.copy().reset_index(drop=True)
        label_series = pd.Series(labels + [None] * (len(df_out) - len(labels)))
        df_out.insert(0, 'cluster', label_series)
    else:
        df_out = df.copy().reset_index(drop=True)
        df_out.insert(0, 'cluster', labels)  # Insertar la columna de clusters al inicio

    export_format = request.args.get('format', 'csv')

    if export_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_out.to_excel(writer, index=False, sheet_name='Resultados')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='resultados_clusters.xlsx')
    else:
        output = io.StringIO()
        df_out.to_csv(output, index=False)
        output.seek(0)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='resultados_clusters.csv')

@app.route('/api/predict', methods=['POST'])
def api_predict():
    """
    Simulador: recibe las respuestas de un usuario nuevo y predice a qué clúster pertenece.
    Usa el modelo actualmente cargado en memoria para la predicción instantánea.
    """
    data = request.json
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No hay ningún modelo entrenado. Entrena o carga uno primero.'}), 400
        
    model = app.config['CURRENT_MODEL']
    features = model.features
    
    if not features:
        return jsonify({'error': 'El modelo no tiene columnas configuradas.'}), 400
        
    row_data = {}
    for f in features:
        if f not in data:
            return jsonify({'error': f'Falta la respuesta para la pregunta: {f}'}), 400
        row_data[f] = float(data[f])
        
    # Crear un DataFrame de una sola fila con las respuestas del usuario
    df_row = pd.DataFrame([row_data])
    
    try:
        cluster_id = model.predict(df_row)  # Comparar contra los centroides y asignar al más cercano
        return jsonify({'cluster': cluster_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
    """
    Descarga el dataset activo (con los filtros aplicados) en formato CSV o Excel.
    """
    df = get_data()
    df = apply_dynamic_filters(df, request.args)
        
    export_format = request.args.get('format', 'csv')
    
    if export_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='datos_exportados.xlsx')
    else:
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='datos_exportados.csv')

@app.route('/api/download_model', methods=['GET'])
def api_download_model():
    """
    Descarga físicamente el archivo .pkl de un modelo guardado al equipo del usuario.
    """
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'No se proporcionó el nombre del archivo.'}), 400
        
    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Archivo de modelo no encontrado.'}), 404
        
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
