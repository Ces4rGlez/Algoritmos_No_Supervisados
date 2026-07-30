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
                currentPage = 1;
                // Clear old dynamic filters so they regenerate
                document.getElementById('dynamic-filters-container').innerHTML = '';
                loadData();
                loadStats();
            } else {
                uploadStatus.style.color = '#ef4444';
                uploadStatus.innerHTML = `Error: ${result.error}`;
            }
        } catch (err) {
            uploadStatus.style.color = '#ef4444';
            uploadStatus.innerHTML = `Error de conexión: ${err.message}`;
        }
    });

    // --- Dashboard Logic ---
    let currentPage = 1;
    let histChart = null;
    let dynamicCharts = []; // store instances of dynamic charts to destroy them later

    const btnApplyFilters = document.getElementById('btn-apply-filters');
    const btnPrevPage = document.getElementById('btn-prev-page');
    const btnNextPage = document.getElementById('btn-next-page');
    const btnFirstPage = document.getElementById('btn-first-page');
    const btnLastPage = document.getElementById('btn-last-page');
    let totalPages = 1;

    if (btnApplyFilters) {
        btnApplyFilters.addEventListener('click', () => {
            currentPage = 1;
            loadData();
            loadStats();
        });
    }

    if (btnFirstPage) btnFirstPage.addEventListener('click', () => { if (currentPage > 1) { currentPage = 1; loadData(); } });
    if (btnLastPage) btnLastPage.addEventListener('click', () => { if (currentPage < totalPages) { currentPage = totalPages; loadData(); } });
    if (btnPrevPage) btnPrevPage.addEventListener('click', () => { if (currentPage > 1) { currentPage--; loadData(); } });
    if (btnNextPage) btnNextPage.addEventListener('click', () => { if (currentPage < totalPages) { currentPage++; loadData(); } });

    const btnDownload = document.getElementById('btn-download-data');
    if (btnDownload) {
        btnDownload.addEventListener('click', () => {
            let url = `/api/download?${getFiltersParams()}&format=csv`;
            window.open(url, '_blank');
        });
    }

    const btnDownloadExcel = document.getElementById('btn-download-excel');
    if (btnDownloadExcel) {
        btnDownloadExcel.addEventListener('click', () => {
            let url = `/api/download?${getFiltersParams()}&format=excel`;
            window.open(url, '_blank');
        });
    }

    const btnDownloadPdf = document.getElementById('btn-download-pdf');
    if (btnDownloadPdf) {
        btnDownloadPdf.addEventListener('click', () => {
            let url = `/api/report/pdf?${getFiltersParams()}`;
            window.open(url, '_blank');
        });
    }

    function getFiltersParams() {
        const filters = [];
        const selects = document.querySelectorAll('#dynamic-filters-container select');
        selects.forEach(select => {
            if (select.value && select.value !== 'Todos') {
                filters.push(`${encodeURIComponent(select.name)}=${encodeURIComponent(select.value)}`);
            }
        });
        return filters.join('&');
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
            renderDynamicFilters(result.filters_info);

            const trObj = document.getElementById('total-records');
            if (trObj) trObj.innerText = result.total;
            const piObj = document.getElementById('page-indicator');
            if (piObj) piObj.innerText = `Pág. ${result.page} / ${Math.ceil(result.total / result.per_page)}`;
            
            totalPages = Math.ceil(result.total / result.per_page);
            if (btnFirstPage) btnFirstPage.disabled = result.page === 1;
            if (btnPrevPage) btnPrevPage.disabled = result.page === 1;
            if (btnNextPage) btnNextPage.disabled = result.page >= totalPages;
            if (btnLastPage) btnLastPage.disabled = result.page >= totalPages;

        } catch (error) {
            console.error("Error loading data:", error);
        }
    }

    function renderDynamicFilters(filtersInfo) {
        const container = document.getElementById('dynamic-filters-container');
        if (!container) return;
        
        // Only generate filters if container is empty (don't overwrite user selections when filtering)
        if (container.children.length > 0) return;
        
        for (const [colName, uniqueValues] of Object.entries(filtersInfo)) {
            const group = document.createElement('div');
            group.className = 'filter-group';
            
            const label = document.createElement('label');
            label.innerText = colName;
            
            const select = document.createElement('select');
            select.name = colName;
            
            const defaultOpt = document.createElement('option');
            defaultOpt.value = 'Todos';
            defaultOpt.innerText = 'Todos';
            select.appendChild(defaultOpt);
            
            uniqueValues.forEach(val => {
                const opt = document.createElement('option');
                opt.value = val;
                opt.innerText = val;
                select.appendChild(opt);
            });
            
            group.appendChild(label);
            group.appendChild(select);
            container.appendChild(group);
        }
    }

    function updateFeaturesCheckboxes(num_cols) {
        const container = document.getElementById('features-container');
        if(!container) return;
        container.innerHTML = '';

        if (!num_cols || num_cols.length === 0) {
            container.innerHTML = '<span style="color:#ef4444">No se encontraron columnas numéricas para analizar.</span>';
            return;
        }

        // Prioritize MBTI columns if they exist, otherwise select top 5
        const mbtiCols = ['energia_score', 'percepcion_score', 'decision_score', 'estilo_score'];
        const hasMbti = mbtiCols.every(c => num_cols.includes(c));
        
        num_cols.forEach((col, idx) => {
            let isChecked = false;
            if (hasMbti) {
                isChecked = mbtiCols.includes(col);
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
        if (!thead || !tbody) return;

        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (data.length === 0 || columns.length === 0) return;

        // Header
        const trHead = document.createElement('tr');
        columns.forEach(col => { 
            const th = document.createElement('th');
            th.innerText = col;
            trHead.appendChild(th);
        });
        thead.appendChild(trHead);

        // Body
        data.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(col => {
                const td = document.createElement('td');
                let val = row[col];
                if (typeof val === 'number') val = val.toFixed(2).replace('.00', '');
                td.innerText = val !== null && val !== undefined ? val : '';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    async function loadStats() {
        try {
            const params = getFiltersParams();
            const res = await fetch(`/api/stats?${params}&t=${new Date().getTime()}`);
            if (!res.ok) throw new Error('Network response was not ok');
            const stats = await res.json();
            
            renderKpiCards(stats.desc_stats);
            renderDescriptiveStatsTable(stats.desc_stats);
            renderInterpretations(stats.interpretations);
            renderDynamicChartsGrid(stats);
            
        } catch (error) {
            console.error("Error loading stats:", error);
        }
    }

    function renderKpiCards(descStats) {
        const container = document.getElementById('kpi-cards-container');
        if (!container) return;
        container.innerHTML = '';

        let count = 0;
        for (const [key, s] of Object.entries(descStats)) {
            if (count >= 4) break; // Maximum of 4 KPI cards
            const card = document.createElement('div');
            card.className = 'card'; // using card class for better styling matching existing UI
            card.style.padding = '1.5rem';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.justifyContent = 'center';

            card.innerHTML = `
                <span style="color: #64748b; font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">Promedio de ${key}</span>
                <span style="font-size: 2rem; font-weight: 700; color: #2563eb; margin: 0.5rem 0;">${s.mean.toFixed(2)}</span>
                <span style="font-size: 0.85rem; color: #64748b;">Desviación Est.: &plusmn;${s.std.toFixed(2)}</span>
            `;
            container.appendChild(card);
            count++;
        }
    }

    function renderDescriptiveStatsTable(descStats) {
        const tbody = document.getElementById('stats-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        for (const [colName, s] of Object.entries(descStats)) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600; text-align:left;">${colName}</td>
                <td>${s.min.toFixed(2)}</td>
                <td>${s.max.toFixed(2)}</td>
                <td>${s.range.toFixed(2)}</td>
                <td>${s.mean.toFixed(2)}</td>
                <td>${s.median.toFixed(2)}</td>
                <td>${s.std.toFixed(2)}</td>
                <td>${(s.var !== undefined ? s.var : 0).toFixed(2)}</td>
                <td>${s.skew.toFixed(2)}</td>
                <td>${(s.kurtosis !== undefined ? s.kurtosis : 0).toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
        }
    }

    function renderInterpretations(interpretations) {
        const list = document.getElementById('interpretations-list');
        if (!list) return;
        list.innerHTML = '';
        
        interpretations.forEach(text => {
            const li = document.createElement('li');
            li.style.marginBottom = '0.5rem';
            li.innerText = text;
            list.appendChild(li);
        });
    }

    function renderDynamicChartsGrid(stats) {
        const grid = document.getElementById('dynamic-charts-grid');
        if (!grid) return;
        
        // Destroy old charts
        dynamicCharts.forEach(c => c.destroy());
        dynamicCharts = [];
        grid.innerHTML = '';

        Chart.defaults.color = '#64748b';
        Chart.defaults.font.family = 'Inter';
        
        const colors = [
            '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd',
            '#1e40af', '#1e3a8a', '#475569', '#64748b',
            '#16a34a', '#22c55e', '#4ade80', '#86efac',
            '#f59e0b', '#d97706', '#b45309', '#78350f'
        ];

        // 1. Render Histogram with Chip Selector (Space-saving but fast)
        if (stats.hist_data_all && Object.keys(stats.hist_data_all).length > 0) {
            const histCard = document.createElement('div');
            histCard.className = 'card chart-card';
            histCard.style.gridColumn = '1 / -1'; // span full width if needed, or let it flow
            
            // Create a container for the chips
            const chipContainer = document.createElement('div');
            chipContainer.style.display = 'flex';
            chipContainer.style.gap = '0.5rem';
            chipContainer.style.flexWrap = 'wrap';
            chipContainer.style.marginBottom = '1rem';
            
            const canvasId = `dynamic-chart-hist-main`;
            histCard.innerHTML = `
                <div class="card-header" style="flex-direction: column; align-items: flex-start; gap: 0.5rem;">
                    <h3>Distribución de Variables</h3>
                    <div id="hist-chips" style="display:flex; gap:0.5rem; flex-wrap:wrap; width:100%;"></div>
                </div>
                <div class="chart-wrap"><canvas id="${canvasId}"></canvas></div>
            `;
            grid.appendChild(histCard);
            
            const chipsDiv = histCard.querySelector('#hist-chips');
            const ctx = document.getElementById(canvasId).getContext('2d');
            let mainHistChart = null;

            const renderSingleHist = (colName, histData) => {
                const labels = [];
                for (let i = 0; i < histData.bins.length - 1; i++) {
                    labels.push(`${histData.bins[i].toFixed(1)} - ${histData.bins[i + 1].toFixed(1)}`);
                }
                
                if (mainHistChart) mainHistChart.destroy();
                
                mainHistChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                type: 'line',
                                label: 'Tendencia',
                                data: histData.counts,
                                borderColor: '#ef4444',
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true,
                                pointRadius: 0
                            },
                            {
                                type: 'bar',
                                label: `Frecuencia (${colName})`,
                                data: histData.counts,
                                backgroundColor: 'rgba(37, 99, 235, 0.6)',
                                borderColor: '#2563eb',
                                borderWidth: 1,
                                borderRadius: 4
                            }
                        ]
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
                
                // Keep track to destroy later
                if (!dynamicCharts.includes(mainHistChart)) {
                    dynamicCharts.push(mainHistChart);
                }
            };

            // Create buttons for each variable
            let firstCol = null;
            for (const [colName, histData] of Object.entries(stats.hist_data_all)) {
                if (!firstCol) firstCol = { colName, histData };
                
                const btn = document.createElement('button');
                btn.className = 'btn btn-secondary';
                btn.style.padding = '0.25rem 0.75rem';
                btn.style.fontSize = '0.8rem';
                btn.style.borderRadius = '99px';
                btn.innerText = colName;
                
                btn.addEventListener('click', (e) => {
                    // Remove active style from all
                    Array.from(chipsDiv.children).forEach(c => {
                        c.style.backgroundColor = 'var(--bg-alt)';
                        c.style.color = 'var(--text-main)';
                    });
                    // Set active style for clicked
                    btn.style.backgroundColor = 'var(--primary)';
                    btn.style.color = '#fff';
                    
                    renderSingleHist(colName, histData);
                });
                
                chipsDiv.appendChild(btn);
            }
            
            // Render the first one by default
            if (firstCol) {
                chipsDiv.firstChild.style.backgroundColor = 'var(--primary)';
                chipsDiv.firstChild.style.color = '#fff';
                renderSingleHist(firstCol.colName, firstCol.histData);
            }
        }
        
        // 2. Render Pie Charts for Categorical Data
        let chartIndex = 0;
        for (const [colName, dist] of Object.entries(stats.cat_dist)) {
            if (chartIndex >= 3) break; // limit to 3 categorical charts to avoid clutter
            const card = document.createElement('div');
            card.className = 'card chart-card';
            const canvasId = `dynamic-chart-cat-${chartIndex}`;
            card.innerHTML = `
                <div class="card-header">
                    <h3>Distribución: ${colName}</h3>
                </div>
                <div class="chart-wrap"><canvas id="${canvasId}"></canvas></div>
            `;
            grid.appendChild(card);
            
            const ctx = document.getElementById(canvasId).getContext('2d');
            const c = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: Object.keys(dist),
                    datasets: [{
                        data: Object.values(dist),
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
            dynamicCharts.push(c);
            chartIndex++;
        }
    }


    // --- Training Logic ---
    const btnTrain = document.getElementById('btn-train');
    const loader = document.getElementById('training-loader');
    const saveModelPanel = document.getElementById('save-model-panel');
    const varianceVal = document.getElementById('variance-val');
    const btnSaveModel = document.getElementById('btn-save-model');
    const saveMsg = document.getElementById('save-msg');

    let clustersChart = null;

    if (btnTrain) btnTrain.addEventListener('click', async () => {
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
            if (result.z_pca && result.z_pca.length > 0) {
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

                    let color = '#ef4444'; // red
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

    if(btnSaveModel) btnSaveModel.addEventListener('click', async () => {
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
        } catch (e) {
            alert("Error al guardar: " + e.message);
        } finally {
            btnSaveModel.disabled = false;
        }
    });

    // ── Load saved model ──────────────────────────────────────────────────
    let savedModelsList = [];
    
    async function refreshModelList() {
        const sel = document.getElementById('model-select');
        const selCompA = document.getElementById('compare-model-a');
        const selCompB = document.getElementById('compare-model-b');
        
        if (!sel) return;
        try {
            const res = await fetch('/api/list_models');
            savedModelsList = await res.json();
            
            const renderOptions = (selectElement) => {
                if (!selectElement) return;
                selectElement.innerHTML = '<option value="">-- Selecciona un modelo --</option>';
                if (savedModelsList.length === 0) {
                    selectElement.innerHTML += '<option disabled>No hay modelos guardados aún</option>';
                    return;
                }
                savedModelsList.forEach(m => {
                    const algo = m.metadata.algorithm || '';
                    const ts = m.metadata.timestamp ? m.metadata.timestamp.slice(0, 16).replace('T', ' ') : '';
                    const desc = m.metadata.description ? ` — ${m.metadata.description}` : '';
                    const opt = document.createElement('option');
                    opt.value = m.filename;
                    opt.textContent = `${m.filename}  (${algo.toUpperCase()} · ${ts}${desc})`;
                    selectElement.appendChild(opt);
                });
            };
            
            renderOptions(sel);
            renderOptions(selCompA);
            renderOptions(selCompB);
            
        } catch (e) {
            console.error('Error listing models:', e);
        }
    }

    const btnRefresh = document.getElementById('btn-refresh-models');
    if (btnRefresh) btnRefresh.addEventListener('click', refreshModelList);

    const btnLoad = document.getElementById('btn-load-model');
    if (btnLoad) btnLoad.addEventListener('click', async () => {
        const filename = document.getElementById('model-select').value;
        const msgEl = document.getElementById('load-model-msg');
        if (!filename) { alert('Selecciona un modelo primero.'); return; }

        const btn = document.getElementById('btn-load-model');
        btn.disabled = true;
        btn.textContent = 'Cargando...';
        msgEl.classList.add('hidden');

        try {
            const res = await fetch('/api/load_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            });
            const result = await res.json();
            if (!res.ok) throw new Error(result.error);

            msgEl.innerHTML = ` Modelo cargado: <strong>${filename}</strong>. Revisa la pestaña Resultados.`;
            msgEl.classList.remove('hidden');

            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector('[data-tab="results"]').classList.add('active');
            document.getElementById('results').classList.add('active');

            document.getElementById('variance-val').innerText = (result.explained_variance * 100).toFixed(1);
            renderClustersChart(result.x_pca, result.y_pca, result.labels);
            if (result.z_pca && result.z_pca.length > 0) render3DChart(result.x_pca, result.y_pca, result.z_pca, result.labels);
            if (result.features) buildPredictionForm(result.features);

            const compPanel = document.getElementById('composition-panel');
            const compTbody = document.getElementById('composition-tbody');
            if (result.composition && result.composition.length > 0) {
                compPanel.style.display = 'block';
                compTbody.innerHTML = '';

                result.composition.forEach(comp => {
                    const tr = document.createElement('tr');
                    let color = '#ef4444';
                    if (comp.purity >= 80) color = '#16a34a';
                    else if (comp.purity >= 50) color = '#f59e0b';

                    tr.innerHTML = `
                        <td><strong>Clúster ${comp.cluster}</strong></td>
                        <td>${comp.size}</td>
                        <td>${comp.dominant_label} (de '${comp.eval_col}')</td>
                        <td>
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-weight: 600; color: ${color};">${comp.purity}%</span>
                                <div class="progress-bar-bg" style="flex: 1; height: 6px; background: var(--bg-alt); border-radius: 99px; overflow: hidden;">
                                    <div class="progress-bar-fill" style="width: ${comp.purity}%; height: 100%; background: ${color}; border-radius: 99px;"></div>
                                </div>
                            </div>
                        </td>
                    `;
                    compTbody.appendChild(tr);
                });
            } else {
                compPanel.style.display = 'none';
            }
        } catch (e) {
            alert('Error al cargar el modelo: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg> Cargar Modelo`;
        }
    });

    const btnDownloadModel = document.getElementById('btn-download-model');
    if (btnDownloadModel) {
        btnDownloadModel.addEventListener('click', () => {
            const filename = document.getElementById('model-select').value;
            if (!filename) { alert('Selecciona un modelo primero.'); return; }
            window.open(`/api/download_model?filename=${encodeURIComponent(filename)}`, '_blank');
        });
    }

    // ── Download results ────────────────────────────────────────────────────
    const btnDownloadResults = document.getElementById('btn-download-results');
    if (btnDownloadResults) {
        btnDownloadResults.addEventListener('click', () => {
            window.open('/api/download_results?format=csv', '_blank');
        });
    }

    const btnDownloadResultsExcel = document.getElementById('btn-download-results-excel');
    if (btnDownloadResultsExcel) {
        btnDownloadResultsExcel.addEventListener('click', () => {
            window.open('/api/download_results?format=excel', '_blank');
        });
    }

    // ── Comparison Logic ────────────────────────────────────────────────────
    const btnRunComparison = document.getElementById('btn-run-comparison');
    if (btnRunComparison) {
        btnRunComparison.addEventListener('click', () => {
            const valA = document.getElementById('compare-model-a').value;
            const valB = document.getElementById('compare-model-b').value;
            
            if (!valA || !valB) {
                alert('Por favor selecciona ambos modelos (A y B) para comparar.');
                return;
            }
            if (valA === valB) {
                alert('Selecciona modelos diferentes para hacer una comparación útil.');
                return;
            }
            
            const modelA = savedModelsList.find(m => m.filename === valA);
            const modelB = savedModelsList.find(m => m.filename === valB);
            
            if (!modelA || !modelB) return;
            
            document.getElementById('comparison-results').classList.remove('hidden');
            
            const tbody = document.getElementById('comparison-tbody');
            tbody.innerHTML = '';
            
            const metrics = [
                { label: 'Algoritmo', key: 'algorithm', format: val => (val || '').toUpperCase() },
                { label: 'Fecha de Entrenamiento', key: 'timestamp', format: val => val ? val.slice(0, 16).replace('T', ' ') : 'N/A' },
                { label: 'Descripción', key: 'description', format: val => val || 'Sin descripción' },
                { label: 'Características (Features)', key: 'features', format: val => val ? val.join(', ') : 'N/A' }
            ];
            
            // Render textual metadata
            metrics.forEach(m => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600;">${m.label}</td>
                    <td>${m.format(modelA.metadata[m.key])}</td>
                    <td>${m.format(modelB.metadata[m.key])}</td>
                `;
                tbody.appendChild(tr);
            });
            
            // Render Silhouette Score and visually indicate the winner
            let silA = modelA.metadata.silhouette;
            let silB = modelB.metadata.silhouette;
            
            silA = (silA !== undefined && silA !== null) ? parseFloat(silA) : null;
            silB = (silB !== undefined && silB !== null) ? parseFloat(silB) : null;
            
            const silAText = silA !== null ? silA.toFixed(4) : 'N/A (Modelo Antiguo)';
            const silBText = silB !== null ? silB.toFixed(4) : 'N/A (Modelo Antiguo)';
            
            let silAStyle = '';
            let silBStyle = '';
            
            if (silA !== null && silB !== null) {
                if (silA > silB) silAStyle = 'font-weight: bold; color: #16a34a; background-color: #f0fdf4; border-radius: 4px; padding: 2px 6px;';
                else if (silB > silA) silBStyle = 'font-weight: bold; color: #16a34a; background-color: #f0fdf4; border-radius: 4px; padding: 2px 6px;';
            }
            
            const trSil = document.createElement('tr');
            trSil.innerHTML = `
                <td style="font-weight: 600; font-size: 1.1em;">Puntuación de Silueta <br><small style="font-weight: normal; font-size: 0.8em; color: var(--text-muted);">(Más cerca de 1 es mejor)</small></td>
                <td><span style="${silAStyle}">${silAText}</span></td>
                <td><span style="${silBStyle}">${silBText}</span></td>
            `;
            tbody.appendChild(trSil);
        });
    }

    // Load model list on page load
    refreshModelList();

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
                        labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } }
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
        if(typeof Plotly === 'undefined') return;
        
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

        Plotly.newPlot('chart-3d', [trace], layout, { responsive: true });
    }

    function buildPredictionForm(features) {
        const panel = document.getElementById('prediction-simulator-panel');
        const container = document.getElementById('prediction-form-container');
        const resDiv = document.getElementById('prediction-result');
        const btnPredict = document.getElementById('btn-predict-cluster');
        
        if(!panel || !container || !btnPredict) return;

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
                if (inp.value === '') valid = false;
                data[inp.getAttribute('data-feature')] = parseFloat(inp.value);
            });

            if (!valid) {
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

                if (!res.ok) throw new Error(result.error);

                resDiv.className = 'prediction-result success-result';
                resDiv.style.display = 'flex';
                resDiv.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                    </svg>
                    <div>Basado en tus respuestas, perteneces matemáticamente al <strong>Clúster ${result.cluster}</strong>.</div>
                `;

            } catch (e) {
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
