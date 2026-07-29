# DataInsights — ML Analytics for MBTI Personality

Este proyecto es una plataforma interactiva que aplica **Inteligencia Artificial** (Machine Learning no supervisado) a una base de datos de test de personalidad (MBTI). Permite analizar, filtrar y descubrir patrones ocultos (clústeres) en los perfiles psicológicos sin etiquetas previas.

##  Características Principales

1. **Dashboard Analítico**: Explora el set de datos con gráficos dinámicos (histogramas, gráficos de dispersión, radar) que se actualizan en tiempo real usando filtros por Edad, Género y Tipo MBTI.
2. **Entrenamiento de Machine Learning**:
   * Utiliza **K-Means Clustering** y **Gaussian Mixture Models (GMM)** para agrupar usuarios basados en características matemáticas (puntajes numéricos de personalidad).
   * Reducción de dimensionalidad automática usando **Análisis de Componentes Principales (PCA)**.
3. **Visualización de Resultados (PCA)**:
   * Visualizador de dispersión 2D de clústeres.
   * Visualizador interactivo en 3D del espacio latente (Plotly).
   * Simulador predictivo: ingresa nuevas calificaciones manuales y descubre a qué clúster matemático perteneces en tiempo real.
4. **Generador de Datos Personalizados**: Incluye un script generador de datos hiper-realistas para escalar de los 54 perfiles originales a 10,000 registros con ruido gaussiano estadístico.
5. **Exportación e Importación Profesional**:
    * **Guardar e Importar Modelos (.pkl)**: Puedes guardar un algoritmo entrenado para uso posterior y volverlo a cargar sin necesidad de reentrenar todo desde cero, viendo sus gráficas y usando su simulador de inmediato.
    * **Exportar Datos**: Exporta el dataset base filtrado o el dataset resultante con los clústeres asignados, tanto en formato `.csv` como en `.xlsx` (Excel).

##  Tecnologías Utilizadas

* **Backend**: Python, Flask, Pandas
* **Machine Learning**: Scikit-Learn (`KMeans`, `GaussianMixture`, `PCA`, `StandardScaler`)
* **Frontend**: HTML5, CSS3 (Custom Premium Theme), Vanilla JavaScript
* **Visualización de Datos**: Chart.js, Plotly.js

---

## - Instalación y Uso

### 1. Clonar el repositorio
Si usas Git, clona el repositorio en tu máquina local:
```bash
git clone <URL_DE_TU_REPOSITORIO>
cd AppTestPersonalidad
```

### 2. Crear y activar un entorno virtual (Recomendado)
Es una buena práctica encapsular las dependencias usando `venv`:

**En Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**En macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias
Instala los paquetes necesarios para correr la aplicación:
```bash
pip install Flask pandas numpy scikit-learn joblib openpyxl
```
*(Nota: Si usas Windows, asegúrate de que estás en el entorno virtual activado al correr el comando).*

### 4. Generar el dataset (Opcional si ya existe)
Si el archivo `datos_mbti_10k.csv` no existe o quieres generar uno nuevo, ejecuta el script de generación:
```bash
python data_generator.py
```
*Este paso toma los 54 nombres originales y los expande hiper-escalando el dataset a 10,000 registros.*

### 5. Iniciar la aplicación Flask
Arranca el servidor local:
```bash
python app.py
```

### 6. Acceder al aplicativo web
Abre tu navegador web favorito (Chrome, Firefox, Edge, Safari) e ingresa a la siguiente dirección:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

##  Estructura del Proyecto

```
AppTestPersonalidad/
│
├── app.py                  # Servidor backend de Flask (Rutas y API)
├── ml_models.py            # Lógica y clases de Machine Learning (K-Means/GMM, PCA)
├── data_generator.py       # Script generador de datos (aumentación estadística)
├── datos_mbti_10k.csv      # Base de datos predeterminada (10,000 registros)
│
├── templates/
│   └── index.html          # Interfaz web principal (Dashboard y pestañas)
│
├── static/
│   ├── style.css           # Hoja de estilos con variables UI modernas
│   └── app.js              # Lógica de frontend, llamadas a la API y gráficas Chart.js/Plotly
│
├── uploads/                # Carpeta para archivos CSV subidos temporalmente por usuarios
├── models/                 # Carpeta para guardar los modelos .joblib entrenados y metadatos
└── .gitignore              # Archivos omitidos en Git
```
