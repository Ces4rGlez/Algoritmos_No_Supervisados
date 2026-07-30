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

app = Flask(__name__)
app.config['MODEL_DIR'] = 'models'
app.config['UPLOAD_FOLDER'] = 'uploads'

for folder in [app.config['MODEL_DIR'], app.config['UPLOAD_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_data():
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
            
    # Fallback to generated data
    data_path = 'datos_mbti_10k.csv'
    if not os.path.exists(data_path):
        data_path = '../Cuestionario MBTI - Hoja 1.csv'
    if not os.path.exists(data_path):
        return pd.DataFrame()
    return pd.read_csv(data_path)

def apply_dynamic_filters(df, args):
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
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        # Remove old files
        for old in ['uploaded_dataset.csv', 'uploaded_dataset.xlsx']:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], old)
            if os.path.exists(old_path):
                os.remove(old_path)
                
        ext = '.csv' if file.filename.endswith('.csv') else '.xlsx'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_dataset{ext}')
        file.save(filepath)
        return jsonify({'message': 'File successfully uploaded.'})
    else:
        return jsonify({'error': 'Invalid file format. Only CSV or XLSX allowed.'}), 400

@app.route('/api/data', methods=['GET'])
def api_data():
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data found'}), 404
        
    df = apply_dynamic_filters(df, request.args)
        
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    total_records = len(df)
    
    start = (page - 1) * per_page
    end = start + per_page
    
    # Fill NaN values so jsonify doesn't fail
    df = df.fillna('')
    data = df.iloc[start:end].to_dict(orient='records')
    columns = list(df.columns)
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Provide unique values for filters (max 20 unique values)
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
        'cat_dist': {},
        'desc_stats': {},
        'hist_data': {},
        'hist_col': None,
        'numeric_cols': [],
        'interpretations': []
    }
    
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Distributions for categorical charts
    for col in categorical_cols:
        if 2 <= df[col].nunique() <= 20:
            stats['cat_dist'][col] = df[col].value_counts().to_dict()
                
    # Descriptive Statistics for numeric columns
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
            'range': c_max - c_min,
            'mean': c_mean,
            'median': float(s.median()),
            'std': c_std,
            'var': float(s.var()) if len(s) > 1 else 0.0,
            'skew': float(s.skew()) if len(s) > 2 else 0.0,
            'kurtosis': float(s.kurtosis()) if len(s) > 3 else 0.0
        }
        
        # Simple Interpretation rules
        skew = stats['desc_stats'][c]['skew']
        if skew > 1:
            stats['interpretations'].append(f"La variable '{c}' tiene una asimetría positiva alta (sesgada a la derecha).")
        elif skew < -1:
            stats['interpretations'].append(f"La variable '{c}' tiene una asimetría negativa alta (sesgada a la izquierda).")
            
        if c_std > c_mean and c_mean > 0:
            stats['interpretations'].append(f"La variable '{c}' presenta una alta dispersión (Desviación Estándar mayor que la Media).")
            
    # Histogram data for ALL numerical columns
    stats['hist_data_all'] = {}
    for col in numeric_cols:
        s_hist = df[col].dropna()
        if len(s_hist) > 0:
            hist, bin_edges = np.histogram(s_hist, bins=15)
            stats['hist_data_all'][col] = {
                'counts': hist.tolist(),
                'bins': bin_edges.tolist()
            }
            
    if not stats['interpretations']:
        stats['interpretations'].append("Las variables numéricas muestran una distribución relativamente normal y simétrica.")
            
    return jsonify(stats)

@app.route('/api/report/pdf', methods=['GET'])
def api_report_pdf():
    df = get_data()
    if df.empty:
        return "No data available", 404
        
    df = apply_dynamic_filters(df, request.args)
    
    # Compute stats for the report
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
        return "Error creating PDF", 500

@app.route('/api/train', methods=['POST'])
def api_train():
    data = request.json
    algorithm = data.get('algorithm', 'kmeans')
    n_clusters = int(data.get('n_clusters', 16))
    features = data.get('features', [])
    
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data to train on'}), 404
        
    if not features:
        features = df.select_dtypes(include=[np.number]).columns.tolist()
            
    for f in features:
        if f not in df.columns:
            return jsonify({'error': f'Feature {f} not found in dataset'}), 400
            
    model = MBTIClusterModel()
    try:
        df_ml = df[features].fillna(df[features].mean())
        results = model.train(df_ml, features, algorithm=algorithm, n_clusters=n_clusters)
        
        app.config['CURRENT_MODEL'] = model
        app.config['LAST_LABELS'] = results['labels']
        app.config['LAST_FEATURES'] = features
        
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        eval_col = None
        if len(categorical_cols) > 0:
            for col in categorical_cols:
                if 2 <= df[col].nunique() <= 50:
                    eval_col = col
                    break
                    
        if eval_col:
            composition = []
            df_with_labels = df.copy()
            df_with_labels['cluster'] = results['labels']
            
            for cluster_id in range(n_clusters):
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
            results['composition'] = composition

        if len(results['x_pca']) > 2000:
            indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
            results['x_pca'] = [results['x_pca'][i] for i in indices]
            results['y_pca'] = [results['y_pca'][i] for i in indices]
            results['labels'] = [results['labels'][i] for i in indices]
            
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_model', methods=['POST'])
def api_save_model():
    data = request.json
    description = data.get('description', '')
    
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No model has been trained yet.'}), 400
        
    model = app.config['CURRENT_MODEL']
    filename = f"model_{model.model_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    
    try:
        saved_path = model.save(filepath, description)
        return jsonify({'message': 'Model saved successfully', 'path': saved_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_model', methods=['POST'])
def api_load_model():
    data = request.json
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': 'No filename provided'}), 400

    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': f'Model file not found: {filename}'}), 404

    model = MBTIClusterModel()
    try:
        metadata = model.load(filepath)
    except Exception as e:
        return jsonify({'error': f'Failed to load model: {str(e)}'}), 500

    app.config['CURRENT_MODEL'] = model

    df = get_data()
    if df.empty or not model.features:
        return jsonify({
            'message': 'Model loaded',
            'metadata': metadata,
            'features': model.features
        })

    missing = [f for f in model.features if f not in df.columns]
    if missing:
        return jsonify({
            'error': f'Loaded model requires features not in current dataset: {missing}'
        }), 400

    df_ml = df[model.features].fillna(df[model.features].mean())
    X_pca = model.pca.transform(df_ml)
    labels = model.model.predict(df_ml).tolist()
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
    
    if len(results['x_pca']) > 2000:
        indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
        results['x_pca']  = [results['x_pca'][i]  for i in indices]
        results['y_pca']  = [results['y_pca'][i]  for i in indices]
        results['labels'] = [results['labels'][i]  for i in indices]

    return jsonify(results)

@app.route('/api/list_models', methods=['GET'])
def api_list_models():
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
    files.sort(key=lambda x: x['filename'], reverse=True)
    return jsonify(files)

@app.route('/api/download_results', methods=['GET'])
def api_download_results():
    if 'LAST_LABELS' not in app.config:
        return jsonify({'error': 'No clustering results available.'}), 400

    df = get_data()
    labels = app.config['LAST_LABELS']

    if len(labels) != len(df):
        df_out = df.copy().reset_index(drop=True)
        label_series = pd.Series(labels + [None] * (len(df_out) - len(labels)))
        df_out.insert(0, 'cluster', label_series)
    else:
        df_out = df.copy().reset_index(drop=True)
        df_out.insert(0, 'cluster', labels)

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
    data = request.json
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No model has been trained yet.'}), 400
        
    model = app.config['CURRENT_MODEL']
    features = model.features
    
    if not features:
        return jsonify({'error': 'Model has no features configured.'}), 400
        
    row_data = {}
    for f in features:
        if f not in data:
            return jsonify({'error': f'Missing feature: {f}'}), 400
        row_data[f] = float(data[f])
        
    df_row = pd.DataFrame([row_data])
    
    try:
        cluster_id = model.predict(df_row)
        return jsonify({'cluster': cluster_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
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
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
        
    filepath = os.path.join(app.config['MODEL_DIR'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Model file not found'}), 404
        
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
