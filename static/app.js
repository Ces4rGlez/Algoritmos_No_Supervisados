document.addEventListener('DOMContentLoaded', () => {
    // --- Navigation (Tabs) ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(t => t.classList.remove('active'));
            
            btn.classList.add('active');
            const targetTab = btn.getAttribute('data-tab');
            document.getElementById(targetTab).classList.add('active');
            
            if (targetTab === 'dashboard') {
                loadData();
                loadStats();
            }
        });
    });

    // --- File Upload Logic ---
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        uploadStatus.classList.remove('hidden');
        uploadStatus.style.color = '#64748b';
        uploadStatus.innerHTML = 'Subiendo archivo...';
        
        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const result = await res.json();
            
            if (res.ok) {
                uploadStatus.style.color = '#16a34a';
                uploadStatus.innerHTML = '¡Archivo subido exitosamente! Los datos se han actualizado.';
                // Reload data to reflect new dataset
                currentPage = 1;
                loadData();
                loadStats();
            } else {
                uploadStatus.style.color = '#ef4444';
                uploadStatus.innerHTML = `Error: ${result.error}`;
            }
        } catch(err) {
            uploadStatus.style.color = '#ef4444';
            uploadStatus.innerHTML = `Error de conexión: ${err.message}`;
        }
    });


    // --- Dashboard Logic ---
    let currentPage = 1;
    let mbtiChart = null;
    let ageChart = null;
    let meansChart = null;
    let histChart = null;

    const btnApplyFilters = document.getElementById('btn-apply-filters');
    const btnPrevPage     = document.getElementById('btn-prev-page');
    const btnNextPage     = document.getElementById('btn-next-page');
    const btnFirstPage    = document.getElementById('btn-first-page');
    const btnLastPage     = document.getElementById('btn-last-page');
    const btnDownload     = document.getElementById('btn-download-data');
    let totalPages = 1;

    btnApplyFilters.addEventListener('click', () => {
        currentPage = 1;
        loadData();
        loadStats();
    });

    btnFirstPage.addEventListener('click', () => { if (currentPage > 1) { currentPage = 1; loadData(); } });
    btnLastPage.addEventListener('click', () => { if (currentPage < totalPages) { currentPage = totalPages; loadData(); } });

    btnPrevPage.addEventListener('click', () => {
        if (currentPage > 1) { currentPage--; loadData(); }
    });

    btnNextPage.addEventListener('click', () => {
        if (currentPage < totalPages) { currentPage++; loadData(); }
    });
    
    btnDownload.addEventListener('click', () => {
        const genero = document.getElementById('filter-gender').value;
        const edad = document.getElementById('filter-age').value;
        const mbti = document.getElementById('filter-mbti').value;
        
        let url = `/api/download?genero=${encodeURIComponent(genero)}&rango_edad=${encodeURIComponent(edad)}&tipo_mbti=${encodeURIComponent(mbti)}`;
        window.open(url, '_blank');
    });

    function getFiltersParams() {
        const genero = document.getElementById('filter-gender').value;
        const edad = document.getElementById('filter-age').value;
        const mbti = document.getElementById('filter-mbti').value;
        return `genero=${encodeURIComponent(genero)}&rango_edad=${encodeURIComponent(edad)}&tipo_mbti=${encodeURIComponent(mbti)}`;
    }

    async function loadData() {
        try {
            const params = getFiltersParams();
            const url = `/api/data?page=${currentPage}&per_page=20&${params}&t=${new Date().getTime()}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error('Network response was not ok');
            const result = await res.json();
            
            renderTable(result.data, result.columns);
            updateFeaturesCheckboxes(result.numeric_columns);
            
            document.getElementById('total-records').innerText = result.total;
            document.getElementById('page-indicator').innerText = `Pág. ${result.page} / ${Math.ceil(result.total / result.per_page)}`;
            totalPages = Math.ceil(result.total / result.per_page);
            
            btnFirstPage.disabled = result.page === 1;
            btnPrevPage.disabled  = result.page === 1;
            btnNextPage.disabled  = result.page >= totalPages;
            btnLastPage.disabled  = result.page >= totalPages;
            
        } catch (error) {
            console.error("Error loading data:", error);
        }
    }
    
    function updateFeaturesCheckboxes(num_cols) {
        const container = document.getElementById('features-container');
        container.innerHTML = '';
        
        if (!num_cols || num_cols.length === 0) {
            container.innerHTML = '<span style="color:#ef4444">No se encontraron columnas numéricas para analizar.</span>';
            return;
        }
        
        // Prioritize MBTI columns if they exist, otherwise select top 4
        const mbtiCols = ['energia_score', 'percepcion_score', 'decision_score', 'estilo_score'];
        const hasMbti = mbtiCols.every(c => num_cols.includes(c));
        
        num_cols.forEach((col, idx) => {
            let isChecked = false;
            if (hasMbti) {
                if (mbtiCols.includes(col)) isChecked = true;
            } else if (idx < 5) {
                isChecked = true;
            }
            
            const label = document.createElement('label');
            label.className = 'feature-checkbox';
            label.innerHTML = `
                <input type="checkbox" class="feature-cb" value="${col}" ${isChecked ? 'checked' : ''}>
                ${col}
            `;
            container.appendChild(label);
        });
    }

    function renderTable(data, columns) {
        const thead = document.getElementById('data-table-head');
        const tbody = document.getElementById('data-table-body');
        
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        if (data.length === 0 || columns.length === 0) return;
        
        // Header
        const trHead = document.createElement('tr');
        columns.slice(0, 10).forEach(col => { // Show max 10 cols to avoid overflow chaos
            const th = document.createElement('th');
            th.innerText = col;
            trHead.appendChild(th);
        });
        if (columns.length > 10) {
            const th = document.createElement('th');
            th.innerText = '...';
            trHead.appendChild(th);
        }
        thead.appendChild(trHead);
        
        // Body
        data.forEach(row => {
            const tr = document.createElement('tr');
            columns.slice(0, 10).forEach(col => {
                const td = document.createElement('td');
                let val = row[col];
                if (typeof val === 'number') val = val.toFixed(2).replace('.00', '');
                td.innerText = val !== null && val !== undefined ? val : '';
                tr.appendChild(td);
            });
            if (columns.length > 10) {
                const td = document.createElement('td');
                td.innerText = '...';
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        });
    }

    async function loadStats() {
        try {
            const params = getFiltersParams();
            const res = await fetch(`/api/stats?${params}&t=${new Date().getTime()}`);
            if (!res.ok) throw new Error('Network response was not ok');
            const stats = await res.json();
            
            
            renderKpiCards(stats.means, stats.stds);
            renderMbtiChart(stats.tipo_dist);
            renderAgeChart(stats.edad_dist);
            renderMeansChart(stats.means);
            if(stats.hist_data && stats.hist_col) {
                renderHistChart(stats.hist_data, stats.hist_col);
            }
        } catch (error) {
            console.error("Error loading stats:", error);
        }
    }

    function renderMbtiChart(tipoDist) {
        const ctx = document.getElementById('chart-mbti').getContext('2d');
        const labels = Object.keys(tipoDist);
        const data = Object.values(tipoDist);
        
        const colors = [
            '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd',
            '#1e40af', '#1e3a8a', '#475569', '#64748b',
            '#0f172a', '#334155', '#94a3b8', '#cbd5e1',
            '#16a34a', '#22c55e', '#4ade80', '#86efac'
        ];

        if (mbtiChart) mbtiChart.destroy();
        
        Chart.defaults.color = '#64748b';
        Chart.defaults.font.family = 'Inter';
        
        mbtiChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { bottom: 8 } },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            padding: 8,
                            font: { size: 11 }
                        }
                    }
                }
            }
        });
    }
    
    function renderAgeChart(edadDist) {
        const ctx = document.getElementById('chart-age').getContext('2d');
        if (!edadDist || Object.keys(edadDist).length === 0) return;
        
        const labels = Object.keys(edadDist);
        const data = Object.values(edadDist);
        
        const colors = ['#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#14b8a6', '#84cc16'];
        
        if (ageChart) ageChart.destroy();
        
        ageChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12, boxHeight: 12, padding: 10, font: { size: 11 } }
                    }
                }
            }
        });
    }

    function renderMeansChart(means) {
        const ctx = document.getElementById('chart-means').getContext('2d');
        const labels = Object.keys(means);
        const data = Object.values(means);
        
        if (meansChart) meansChart.destroy();
        
        meansChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Promedio Numérico',
                    data: data,
                    backgroundColor: 'rgba(37, 99, 235, 0.2)',
                    borderColor: '#2563eb',
                    pointBackgroundColor: '#2563eb',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#2563eb'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: '#e2e8f0' },
                        grid: { color: '#e2e8f0' },
                        pointLabels: { font: { family: 'Inter', size: 11 }, color: '#64748b' },
                        ticks: { backdropColor: 'transparent', color: '#64748b' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    function renderKpiCards(means, stds) {
        const container = document.getElementById('kpi-cards-container');
        container.innerHTML = '';
        
        let count = 0;
        for (const [key, val] of Object.entries(means)) {
            if(count >= 4) break;
            const std = stds[key] || 0;
            const card = document.createElement('div');
            card.className = 'panel';
            card.style.padding = '1.5rem';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            
            card.innerHTML = `
                <span style="color: var(--text-muted); font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">Promedio de ${key}</span>
                <span style="font-size: 2rem; font-weight: 700; color: var(--primary); margin: 0.5rem 0;">${val.toFixed(2)}</span>
                <span style="font-size: 0.85rem; color: #64748b;">Desviación Estándar: &plusmn;${std.toFixed(2)}</span>
            `;
            container.appendChild(card);
            count++;
        }
    }

    function renderHistChart(histData, colName) {
        document.getElementById('hist-title').innerText = `Histograma: ${colName}`;
        const ctx = document.getElementById('chart-hist').getContext('2d');
        
        // Build labels from bin edges
        const labels = [];
        for(let i=0; i<histData.bins.length - 1; i++) {
            labels.push(`${histData.bins[i].toFixed(1)} - ${histData.bins[i+1].toFixed(1)}`);
        }
        
        if (histChart) histChart.destroy();
        
        histChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Frecuencia',
                    data: histData.counts,
                    backgroundColor: 'rgba(37, 99, 235, 0.6)',
                    borderColor: '#2563eb',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true, grid: { color: '#e2e8f0' } }
                }
            }
        });
    }

    // --- Training Logic ---
    const btnTrain = document.getElementById('btn-train');
    const loader = document.getElementById('training-loader');
    const saveModelPanel = document.getElementById('save-model-panel');
    const varianceVal = document.getElementById('variance-val');
    const btnSaveModel = document.getElementById('btn-save-model');
    const saveMsg = document.getElementById('save-msg');
    
    let clustersChart = null;

    btnTrain.addEventListener('click', async () => {
        const algorithm = document.getElementById('algo-select').value;
        const n_clusters = document.getElementById('clusters-input').value;
        
        // Get selected features
        const featureCheckboxes = document.querySelectorAll('.feature-cb:checked');
        const selectedFeatures = Array.from(featureCheckboxes).map(cb => cb.value);
        
        if (selectedFeatures.length < 2) {
            alert('Por favor selecciona al menos 2 características para entrenar el modelo.');
            return;
        }
        
        btnTrain.disabled = true;
        loader.classList.remove('hidden');
        saveModelPanel.classList.add('hidden');
        
        try {
            const res = await fetch('/api/train', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    algorithm, 
                    n_clusters: n_clusters,
                    features: selectedFeatures
                })
            });
            
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Training failed');
            }
            
            const result = await res.json();
            
            varianceVal.innerText = (result.explained_variance * 100).toFixed(2);
            saveModelPanel.classList.remove('hidden');
            saveMsg.classList.add('hidden');
            
            document.querySelector('[data-tab="results"]').click();
            renderClustersChart(result.x_pca, result.y_pca, result.labels);
            if(result.z_pca && result.z_pca.length > 0) {
                render3DChart(result.x_pca, result.y_pca, result.z_pca, result.labels);
            }
            
            buildPredictionForm(selectedFeatures);
            
            const compPanel = document.getElementById('composition-panel');
            const compTbody = document.getElementById('composition-tbody');
            if (result.composition && result.composition.length > 0) {
                compPanel.style.display = 'block';
                compTbody.innerHTML = '';
                
                result.composition.forEach(comp => {
                    const tr = document.createElement('tr');
                    
                    // Assign a color based on purity
                    let color = '#ef4444'; // red (low purity)
                    if (comp.purity >= 80) color = '#16a34a'; // green
                    else if (comp.purity >= 50) color = '#f59e0b'; // yellow
                    
                    tr.innerHTML = `
                        <td><strong>Clúster ${comp.cluster}</strong></td>
                        <td>${comp.size}</td>
                        <td>${comp.dominant_label} (de '${comp.eval_col}')</td>
                        <td>
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-weight: 600; color: ${color};">${comp.purity}%</span>
                                <div style="flex-grow: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden;">
                                    <div style="width: ${comp.purity}%; height: 100%; background: ${color};"></div>
                                </div>
                            </div>
                        </td>
                    `;
                    compTbody.appendChild(tr);
                });
            } else {
                compPanel.style.display = 'none';
            }
            
        } catch (error) {
            alert("Error: " + error.message);
        } finally {
            btnTrain.disabled = false;
            loader.classList.add('hidden');
        }
    });
    
    btnSaveModel.addEventListener('click', async () => {
        const desc = document.getElementById('model-desc').value;
        btnSaveModel.disabled = true;
        
        try {
            const res = await fetch('/api/save_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: desc })
            });
            
            const result = await res.json();
            if (!res.ok) throw new Error(result.error);
            
            saveMsg.innerHTML = result.message + " <br>Ruta: " + result.path;
            saveMsg.classList.remove('hidden');
        } catch(e) {
            alert("Error al guardar: " + e.message);
        } finally {
            btnSaveModel.disabled = false;
        }
    });

    function renderClustersChart(x, y, labels) {
        const ctx = document.getElementById('chart-clusters').getContext('2d');
        
        const datasets = {};
        const palette = [
            '#2563eb', '#dc2626', '#16a34a', '#d97706', '#9333ea', '#db2777', '#0891b2', '#4f46e5',
            '#ca8a04', '#65a30d', '#059669', '#0284c7', '#c026d3', '#e11d48', '#ea580c', '#f59e0b',
            '#4ade80', '#2dd4bf', '#818cf8', '#a78bfa'
        ];
        
        for (let i = 0; i < x.length; i++) {
            const label = labels[i];
            if (!datasets[label]) {
                const color = palette[label % palette.length];
                datasets[label] = {
                    label: `Clúster ${label}`,
                    data: [],
                    backgroundColor: color + '80', // Add transparency
                    borderColor: color,
                    borderWidth: 1,
                    pointRadius: 5,
                    pointHoverRadius: 7
                };
            }
            datasets[label].data.push({ x: x[i], y: y[i] });
        }
        
        const chartData = {
            datasets: Object.values(datasets)
        };

        if (clustersChart) clustersChart.destroy();
        
        clustersChart = new Chart(ctx, {
            type: 'scatter',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 10, usePointStyle: true, font: {size: 11} }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `PCA1: ${ctx.raw.x.toFixed(2)}, PCA2: ${ctx.raw.y.toFixed(2)}`
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Componente Principal 1' }, grid: { color: '#e2e8f0' } },
                    y: { title: { display: true, text: 'Componente Principal 2' }, grid: { color: '#e2e8f0' } }
                }
            }
        });
    }
    
    function render3DChart(x, y, z, labels) {
        const trace = {
            x: x,
            y: y,
            z: z,
            mode: 'markers',
            marker: {
                size: 5,
                color: labels,
                colorscale: 'Jet',
                opacity: 0.8
            },
            type: 'scatter3d'
        };
        
        const layout = {
            margin: { l: 0, r: 0, b: 0, t: 0 },
            scene: {
                xaxis: { title: 'PCA 1' },
                yaxis: { title: 'PCA 2' },
                zaxis: { title: 'PCA 3' }
            }
        };
        
        Plotly.newPlot('chart-3d', [trace], layout, {responsive: true});
    }
    
    function buildPredictionForm(features) {
        const panel = document.getElementById('prediction-simulator-panel');
        const container = document.getElementById('prediction-form-container');
        const resDiv = document.getElementById('prediction-result');
        const btnPredict = document.getElementById('btn-predict-cluster');
        
        panel.style.display = 'block';
        container.innerHTML = '';
        resDiv.innerHTML = '';
        resDiv.style.display = 'none';
        
        features.forEach(f => {
            const div = document.createElement('div');
            div.className = 'pred-form-group';
            div.innerHTML = `
                <label>${f}</label>
                <input type="number" class="pred-input" data-feature="${f}" placeholder="Ej. 10">
            `;
            container.appendChild(div);
        });
        
        // Remove old listeners to avoid multiple fires
        const newBtn = btnPredict.cloneNode(true);
        btnPredict.parentNode.replaceChild(newBtn, btnPredict);
        
        newBtn.addEventListener('click', async () => {
            const inputs = document.querySelectorAll('.pred-input');
            const data = {};
            let valid = true;
            inputs.forEach(inp => {
                if(inp.value === '') valid = false;
                data[inp.getAttribute('data-feature')] = parseFloat(inp.value);
            });
            
            if(!valid) {
                alert('Por favor, llena todos los campos numéricos para hacer la predicción.');
                return;
            }
            
            newBtn.disabled = true;
            newBtn.innerText = 'Calculando...';
            
            try {
                const res = await fetch('/api/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                
                if(!res.ok) throw new Error(result.error);
                
                resDiv.className = 'prediction-result success-result';
                resDiv.style.display = 'flex';
                resDiv.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                    </svg>
                    <div>Basado en tus respuestas, perteneces matemáticamente al <strong>Clúster ${result.cluster}</strong>.</div>
                `;
                
            } catch(e) {
                resDiv.className = 'prediction-result';
                resDiv.style.display = 'flex';
                resDiv.innerHTML = `Error: ${e.message}`;
            } finally {
                newBtn.disabled = false;
                newBtn.innerText = 'Predecir Clúster';
            }
        });
    }

    // Initial load
    loadData();
    loadStats();
});
