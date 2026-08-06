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
    """
    Clase principal que maneja la lógica de Machine Learning del proyecto.
    Se encarga de entrenar el modelo (K-Means), calcular métricas, predecir
    nuevos usuarios y guardar/cargar el modelo entrenado en disco.
    """
    def __init__(self):
        # El modelo matemático real (ej. KMeans de Scikit-Learn)
        self.model = None
        # Tipo de algoritmo usado ('kmeans' o 'gmm')
        self.model_type = None
        # Objeto PCA usado para reducir dimensiones y poder graficar en 2D/3D
        self.pca = None
        # Lista de nombres de las columnas que el modelo usará para aprender (las preguntas del test)
        self.features = []
        # Puntuación de calidad de los clusters (qué tan bien definidos quedaron los grupos)
        self.silhouette = None
        
    def train(self, df, features, algorithm='kmeans', n_clusters=16):
        """
        Método para entrenar el modelo con un dataset (archivo CSV/Excel).
        """
        self.features = features
        self.n_clusters = n_clusters
        
        # Filtramos el dataset para quedarnos solo con las columnas numéricas relevantes
        X = df[features]
        self.model_type = algorithm
        
        # Selección del algoritmo de entrenamiento
        if algorithm == 'kmeans':
            # Configuración de K-Means (16 grupos para los 16 tipos MBTI)
            self.model = KMeans(
                n_clusters=n_clusters, 
                random_state=42, # Semilla fija para que los resultados sean reproducibles
                n_init=10,       # El algoritmo se reinicia 10 veces y guarda el mejor resultado
                max_iter=300,    # Límite máximo de repeticiones para buscar el centroide perfecto
                tol=1e-4         # Tolerancia de movimiento para decidir que ya convergió (terminó)
            )
            # fit_predict asigna a cada persona a un grupo y recalcula los centroides en bucle
            labels = self.model.fit_predict(X)
            
        elif algorithm == 'gmm':
            # Algoritmo alternativo (Gaussian Mixture Models) - no es el principal del proyecto
            self.model = GaussianMixture(n_components=n_clusters, random_state=42)
            labels = self.model.fit_predict(X)
        else:
            raise ValueError("Algoritmo inválido")
            
        # PCA (Análisis de Componentes Principales):
        # Reduce las decenas de dimensiones (preguntas) a solo 2 o 3 para poder dibujarlas en la gráfica
        n_comp = min(3, X.shape[1])
        self.pca = PCA(n_components=n_comp)
        X_pca = self.pca.fit_transform(X)
        
        # Calcula qué porcentaje de la información original logramos conservar al reducir a 2D/3D
        explained_variance = float(sum(self.pca.explained_variance_ratio_))
        
        # Silhouette Score: Mide matemáticamente (del -1 al 1) si los grupos están bien separados entre sí
        if len(set(labels)) > 1:
            try:
                self.silhouette = float(silhouette_score(X, labels))
            except:
                self.silhouette = 0.0
        else:
            self.silhouette = 0.0
            
        # Empaquetamos los resultados para enviarlos a la gráfica del frontend
        results = {
            'labels': labels.tolist(), # A qué grupo pertenece cada persona
            'x_pca': X_pca[:, 0].tolist(), # Coordenada X en la gráfica 2D/3D
            'y_pca': X_pca[:, 1].tolist() if n_comp > 1 else [0]*len(labels), # Coordenada Y
            'z_pca': X_pca[:, 2].tolist() if n_comp > 2 else [0]*len(labels), # Coordenada Z
            'explained_variance': explained_variance,
            'silhouette': self.silhouette,
            'n_clusters': n_clusters,
            'algorithm': algorithm
        }
        return results

    def incremental_train(self, df):
        """
        Aplica aprendizaje incremental (fine-tuning) usando los centroides previos
        como punto de partida inicial. Solo funciona si el modelo actual es KMeans.
        """
        if self.model_type != 'kmeans' or not hasattr(self.model, 'cluster_centers_'):
            raise ValueError("El modelo cargado no soporta aprendizaje incremental (debe ser KMeans previamente entrenado)")
            
        X = df[self.features]
        old_centroids = self.model.cluster_centers_
        
        # Creamos un nuevo modelo empezando exactamente donde se quedó el anterior
        new_model = KMeans(
            n_clusters=self.n_clusters,
            init=old_centroids,
            n_init=1,          # Solo 1 reinicio porque ya le damos los puntos exactos
            max_iter=300,
            random_state=42
        )
        
        labels = new_model.fit_predict(X)
        self.model = new_model
        
        # Re-calcular PCA y Silhouette con los datos nuevos
        n_comp = min(3, X.shape[1])
        self.pca = PCA(n_components=n_comp)
        X_pca = self.pca.fit_transform(X)
        explained_variance = float(sum(self.pca.explained_variance_ratio_))
        
        if len(set(labels)) > 1:
            try:
                self.silhouette = float(silhouette_score(X, labels))
            except:
                self.silhouette = 0.0
        else:
            self.silhouette = 0.0
            
        return {
            'labels': labels.tolist(),
            'x_pca': X_pca[:, 0].tolist(),
            'y_pca': X_pca[:, 1].tolist() if n_comp > 1 else [0]*len(labels),
            'z_pca': X_pca[:, 2].tolist() if n_comp > 2 else [0]*len(labels),
            'explained_variance': explained_variance,
            'silhouette': self.silhouette,
            'n_clusters': self.n_clusters,
            'algorithm': self.model_type
        }

        
    def calculate_optimal_k(self, df, features, algorithm='kmeans', max_k=20):
        X = df[features]
        k_values = list(range(2, max_k + 1))
        inertia = []
        silhouette = []
        
        for k in k_values:
            if algorithm == 'kmeans':
                model = KMeans(n_clusters=k, random_state=42)
                labels = model.fit_predict(X)
                # FÓRMULA DEL CODO (Inercia / WCSS):
                # Calcula la suma de las distancias al cuadrado de cada punto al centroide de su clúster.
                # WCSS = Σ (x_i - μ_k)²
                inertia.append(float(model.inertia_))
            elif algorithm == 'gmm':
                model = GaussianMixture(n_components=k, random_state=42)
                labels = model.fit_predict(X)
                # GMM doesn't have inertia in the same way, we can use negative log-likelihood or AIC/BIC, but to match elbow, we'll use BIC
                inertia.append(float(model.bic(X)))
            else:
                raise ValueError("Invalid algorithm")
                
            if len(set(labels)) > 1:
                # FÓRMULA DEL PUNTAJE DE SILUETA:
                # Calcula s(i) = (b(i) - a(i)) / max(a(i), b(i))
                # a(i): distancia media intra-clúster, b(i): distancia media al clúster más cercano
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
        """
        Método usado por el Simulador para clasificar a un solo usuario nuevo
        sin tener que volver a entrenar el modelo.
        """
        if self.model is None or not self.features:
            raise ValueError("El modelo aún no ha sido entrenado")
            
        # Nos aseguramos de que el nuevo usuario tenga las mismas preguntas exactas que el modelo aprendió
        X = df_row[self.features]
        # predecir en qué grupo cae basado en la distancia al centroide más cercano
        prediction = self.model.predict(X)
        return int(prediction[0])
        
    def save(self, filepath, description=""):
        """
        Guarda ('congela') el modelo entrenado en el disco duro para usarlo en el futuro.
        Cumple con el requisito de 'Guardar modelo'.
        """
        if self.model is None:
            raise ValueError("No hay modelo para guardar")
            
        # Diccionario con todos los datos necesarios para reconstruir el modelo después
        model_data = {
            'model': self.model, # Aquí van empaquetados los 16 centroides finales
            'pca': self.pca,     # Guardamos también el transformador para la gráfica
            'model_type': self.model_type,
            'silhouette': self.silhouette,
            'metadata': {        # Información de contexto para el usuario
                'timestamp': datetime.datetime.now().isoformat(),
                'description': description,
                'algorithm': self.model_type,
                'n_clusters': getattr(self, 'n_clusters', 0),
                'features': self.features,
                'silhouette': self.silhouette
            }
        }
        # Serializamos y guardamos el archivo físico (.pkl)
        joblib.dump(model_data, filepath)
        
        # Guardamos un pequeño archivo .json adicional solo con los metadatos
        # Esto sirve para mostrar la lista de modelos guardados sin tener que cargar los pesados .pkl
        meta_filepath = filepath + '.meta.json'
        with open(meta_filepath, 'w') as f:
            json.dump(model_data['metadata'], f)
            
        return filepath
        
    def load(self, filepath):
        """
        Carga un modelo (.pkl) previamente guardado desde el disco hacia la memoria.
        """
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.pca = model_data['pca']
        self.model_type = model_data['model_type']
        self.silhouette = model_data.get('silhouette', 0.0)
        
        # Recuperar n_clusters del metadata (si es un modelo antiguo que no lo tenía, asume 16 por defecto)
        self.n_clusters = model_data['metadata'].get('n_clusters')
        if not self.n_clusters:
            self.n_clusters = 16
            
        self.features = model_data['metadata'].get('features', [])
        return model_data['metadata']

