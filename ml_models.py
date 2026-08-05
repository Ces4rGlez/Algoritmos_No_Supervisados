import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import joblib
import json
import os
import datetime

class MBTIClusterModel:
    def __init__(self):
        self.model = None
        self.model_type = None
        self.pca = None
        self.features = []
        self.silhouette = None
        
    def train(self, df, features, algorithm='kmeans', n_clusters=16):
        self.features = features
        self.n_clusters = n_clusters
        X = df[features]
        self.model_type = algorithm
        
        if algorithm == 'kmeans':
            self.model = KMeans(n_clusters=n_clusters, random_state=42)
            labels = self.model.fit_predict(X)
        elif algorithm == 'gmm':
            self.model = GaussianMixture(n_components=n_clusters, random_state=42)
            labels = self.model.fit_predict(X)
        else:
            raise ValueError("Invalid algorithm")
            
        # PCA for 2D/3D visualization
        n_comp = min(3, X.shape[1])
        self.pca = PCA(n_components=n_comp)
        X_pca = self.pca.fit_transform(X)
        
        # Calculate explained variance
        explained_variance = float(sum(self.pca.explained_variance_ratio_))
        
        # Calculate silhouette score
        if len(set(labels)) > 1:
            try:
                self.silhouette = float(silhouette_score(X, labels))
            except:
                self.silhouette = 0.0
        else:
            self.silhouette = 0.0
            
        results = {
            'labels': labels.tolist(),
            'x_pca': X_pca[:, 0].tolist(),
            'y_pca': X_pca[:, 1].tolist() if n_comp > 1 else [0]*len(labels),
            'z_pca': X_pca[:, 2].tolist() if n_comp > 2 else [0]*len(labels),
            'explained_variance': explained_variance,
            'silhouette': self.silhouette,
            'n_clusters': n_clusters,
            'algorithm': algorithm
        }
        return results
        
    def calculate_optimal_k(self, df, features, algorithm='kmeans', max_k=20):
        X = df[features]
        k_values = list(range(2, max_k + 1))
        inertia = []
        silhouette = []
        
        for k in k_values:
            if algorithm == 'kmeans':
                model = KMeans(n_clusters=k, random_state=42)
                labels = model.fit_predict(X)
                inertia.append(float(model.inertia_))
            elif algorithm == 'gmm':
                model = GaussianMixture(n_components=k, random_state=42)
                labels = model.fit_predict(X)
                # GMM doesn't have inertia in the same way, we can use negative log-likelihood or AIC/BIC, but to match elbow, we'll use BIC
                inertia.append(float(model.bic(X)))
            else:
                raise ValueError("Invalid algorithm")
                
            if len(set(labels)) > 1:
                sil_score = float(silhouette_score(X, labels))
            else:
                sil_score = 0.0
            silhouette.append(sil_score)
            
        return {
            'k_values': k_values,
            'inertia': inertia,
            'silhouette': silhouette
        }
        
    def predict(self, df_row):
        if self.model is None or not self.features:
            raise ValueError("Model not trained yet")
        # Ensure df_row has exactly the same features in the same order
        X = df_row[self.features]
        prediction = self.model.predict(X)
        return int(prediction[0])
        
    def save(self, filepath, description=""):
        if self.model is None:
            raise ValueError("Model not trained yet")
            
        model_data = {
            'model': self.model,
            'pca': self.pca,
            'model_type': self.model_type,
            'silhouette': self.silhouette,
            'metadata': {
                'timestamp': datetime.datetime.now().isoformat(),
                'description': description,
                'algorithm': self.model_type,
                'n_clusters': getattr(self, 'n_clusters', 0),
                'features': self.features,
                'silhouette': self.silhouette
            }
        }
        joblib.dump(model_data, filepath)
        
        # Save metadata separately for easy access
        meta_filepath = filepath + '.meta.json'
        with open(meta_filepath, 'w') as f:
            json.dump(model_data['metadata'], f)
            
        return filepath
        
    def load(self, filepath):
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.pca = model_data['pca']
        self.model_type = model_data['model_type']
        self.silhouette = model_data.get('silhouette', 0.0)
        self.features = model_data['metadata'].get('features', [])
        return model_data['metadata']

