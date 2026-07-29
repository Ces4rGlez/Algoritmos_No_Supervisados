from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
import os
from ml_models import MBTIClusterModel
import io
import datetime
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MODEL_DIR'] = 'models'
app.config['UPLOAD_FOLDER'] = 'uploads'

for folder in [app.config['MODEL_DIR'], app.config['UPLOAD_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_data():
    uploaded_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.csv')
    if os.path.exists(uploaded_path):
        try:
            return pd.read_csv(uploaded_path)
        except:
            pass
            
    # Fallback to generated data
    data_path = 'datos_mbti_10k.csv'
    if not os.path.exists(data_path):
        data_path = '../Cuestionario MBTI - Hoja 1.csv'
    if not os.path.exists(data_path):
        return pd.DataFrame()
    return pd.read_csv(data_path)

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
        
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_dataset.csv')
        file.save(filepath)
        return jsonify({'message': 'File successfully uploaded.'})
    else:
        return jsonify({'error': 'Invalid file format. Only CSV allowed.'}), 400

@app.route('/api/data', methods=['GET'])
def api_data():
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data found'}), 404
        
    # Generic Filters (we will just apply if the columns exist)
    genero = request.args.get('genero')
    rango_edad = request.args.get('rango_edad')
    tipo_mbti = request.args.get('tipo_mbti')
    
    if genero and genero != 'Todos' and 'genero' in df.columns:
        df = df[df['genero'] == genero]
    if rango_edad and rango_edad != 'Todos' and 'rango_edad' in df.columns:
        df = df[df['rango_edad'] == rango_edad]
    if tipo_mbti and tipo_mbti != 'Todos' and 'tipo_resultante' in df.columns:
        df = df[df['tipo_resultante'] == tipo_mbti]
        
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
    
    # Identify numeric columns for training selection
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    return jsonify({
        'data': data,
        'columns': columns,
        'numeric_columns': numeric_cols,
        'total': total_records,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/stats', methods=['GET'])
def api_stats():
    df = get_data()
    if df.empty:
        return jsonify({'error': 'No data found'}), 404
        
    # Apply Filters
    genero = request.args.get('genero')
    rango_edad = request.args.get('rango_edad')
    tipo_mbti = request.args.get('tipo_mbti')
    
    if genero and genero != 'Todos' and 'genero' in df.columns:
        df = df[df['genero'] == genero]
    if rango_edad and rango_edad != 'Todos' and 'rango_edad' in df.columns:
        df = df[df['rango_edad'] == rango_edad]
    if tipo_mbti and tipo_mbti != 'Todos' and 'tipo_resultante' in df.columns:
        df = df[df['tipo_resultante'] == tipo_mbti]
        
    if df.empty:
        # Prevent errors when stats are empty
        return jsonify({
            'total_records': 0,
            'tipo_dist': {},
            'edad_dist': {},
            'means': {},
            'stds': {},
            'hist_data': {},
            'hist_col': None
        })
        
    stats = {
        'total_records': len(df),
        'tipo_dist': {},
        'edad_dist': {},
        'means': {},
        'stds': {},
        'mins': {},
        'maxs': {},
        'hist_data': {},
        'hist_col': None
    }
    
    # Generic Categorical Stats (Try to find interesting categorical columns)
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    if 'tipo_resultante' in categorical_cols:
        stats['tipo_dist'] = df['tipo_resultante'].value_counts().head(16).to_dict()
    
    if 'rango_edad' in categorical_cols:
        stats['edad_dist'] = df['rango_edad'].value_counts().head(10).to_dict()
        
    # If standard columns don't exist, just grab the first two categorical columns
    if not stats['tipo_dist'] and len(categorical_cols) > 0:
        for col in categorical_cols:
            if 2 <= df[col].nunique() <= 20:
                stats['tipo_dist'] = df[col].value_counts().to_dict()
                break
    
    if not stats['edad_dist'] and len(categorical_cols) > 1:
        for col in categorical_cols:
            if 2 <= df[col].nunique() <= 20 and col != 'tipo_resultante' and not stats['tipo_dist'].keys() == df[col].value_counts().keys():
                stats['edad_dist'] = df[col].value_counts().to_dict()
                break
                
    # Generic Numeric Stats
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Prioritize MBTI columns if they exist
    mbti_cols = ['energia_score', 'percepcion_score', 'decision_score', 'estilo_score']
    
    target_cols = []
    if all(c in numeric_cols for c in mbti_cols):
        target_cols = mbti_cols
    else:
        target_cols = numeric_cols[:4]
        
    for c in target_cols:
        label = c.replace('_score', '').capitalize()
        stats['means'][label] = float(df[c].mean())
        stats['stds'][label] = float(df[c].std())
        stats['mins'][label] = float(df[c].min())
        stats['maxs'][label] = float(df[c].max())
        
    # Histogram data
    if len(numeric_cols) > 0:
        hist_col_req = request.args.get('hist_col', '')
        if hist_col_req and hist_col_req in numeric_cols:
            hist_col = hist_col_req
        else:
            hist_col = numeric_cols[0]
            
        stats['hist_col'] = hist_col
        stats['numeric_cols'] = numeric_cols
        # Calculate bins
        hist, bin_edges = np.histogram(df[hist_col].dropna(), bins=15)
        stats['hist_data'] = {
            'counts': hist.tolist(),
            'bins': bin_edges.tolist()
        }
            
    return jsonify(stats)

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
        # Fallback to MBTI or all numeric
        mbti_cols = ['energia_score', 'percepcion_score', 'decision_score', 'estilo_score']
        if all(c in df.columns for c in mbti_cols):
            features = mbti_cols
        else:
            features = df.select_dtypes(include=[np.number]).columns.tolist()
            
    # Check if features exist
    for f in features:
        if f not in df.columns:
            return jsonify({'error': f'Feature {f} not found in dataset'}), 400
            
    model = MBTIClusterModel()
    try:
        # Impute missing values for ML
        df_ml = df[features].fillna(df[features].mean())
        
        results = model.train(df_ml, features, algorithm=algorithm, n_clusters=n_clusters)
        
        app.config['CURRENT_MODEL'] = model
        app.config['LAST_LABELS'] = results['labels']
        app.config['LAST_FEATURES'] = features
        
        # Calculate cluster composition if a categorical column exists (like tipo_resultante)
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        eval_col = 'tipo_resultante' if 'tipo_resultante' in categorical_cols else None
        if not eval_col and len(categorical_cols) > 0:
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

        # Sample for visualization if too big
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
    """Load a previously saved .pkl model file from the server models/ directory."""
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

    # Re-run predictions on current dataset to rebuild PCA visualisation
    df = get_data()
    if df.empty or not model.features:
        return jsonify({
            'message': 'Model loaded (no dataset available for visualisation)',
            'metadata': metadata,
            'features': model.features
        })

    missing = [f for f in model.features if f not in df.columns]
    if missing:
        return jsonify({
            'error': f'Loaded model requires features not in current dataset: {missing}'
        }), 400

    df_ml = df[model.features].fillna(df[model.features].mean())
    X = df_ml.values
    labels = model.model.predict(df_ml).tolist()
    X_pca = model.pca.transform(df_ml)
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

    # Calculate cluster composition
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    eval_col = 'tipo_resultante' if 'tipo_resultante' in categorical_cols else None
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
        # Sort by cluster id
        composition.sort(key=lambda x: x['cluster'])
        results['composition'] = composition

    # Sample for viz if large
    if len(results['x_pca']) > 2000:
        indices = np.random.choice(len(results['x_pca']), 2000, replace=False)
        results['x_pca']  = [results['x_pca'][i]  for i in indices]
        results['y_pca']  = [results['y_pca'][i]  for i in indices]
        results['labels'] = [results['labels'][i]  for i in indices]

    return jsonify(results)


@app.route('/api/list_models', methods=['GET'])
def api_list_models():
    """Return the list of saved .pkl model files."""
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
    """Download the current dataset with cluster labels appended."""
    if 'LAST_LABELS' not in app.config:
        return jsonify({'error': 'No clustering results available. Train or load a model first.'}), 400

    df = get_data()
    labels = app.config['LAST_LABELS']

    if len(labels) != len(df):
        # Labels are from a sampled subset — just attach what we have
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
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='resultados_clusters.xlsx'
        )
    else:
        output = io.StringIO()
        df_out.to_csv(output, index=False)
        output.seek(0)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='resultados_clusters.csv'
        )


@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.json
    
    if 'CURRENT_MODEL' not in app.config:
        return jsonify({'error': 'No model has been trained yet.'}), 400
        
    model = app.config['CURRENT_MODEL']
    features = model.features
    
    if not features:
        return jsonify({'error': 'Model has no features configured.'}), 400
        
    # Build dataframe for the single row
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
    
    genero = request.args.get('genero')
    rango_edad = request.args.get('rango_edad')
    tipo_mbti = request.args.get('tipo_mbti')
    
    if genero and genero != 'Todos' and 'genero' in df.columns:
        df = df[df['genero'] == genero]
    if rango_edad and rango_edad != 'Todos' and 'rango_edad' in df.columns:
        df = df[df['rango_edad'] == rango_edad]
    if tipo_mbti and tipo_mbti != 'Todos' and 'tipo_resultante' in df.columns:
        df = df[df['tipo_resultante'] == tipo_mbti]
        
    export_format = request.args.get('format', 'csv')
    
    if export_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='datos_exportados.xlsx'
        )
    else:
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='datos_exportados.csv'
        )

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
