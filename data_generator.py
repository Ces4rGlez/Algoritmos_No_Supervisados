import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import random

FIRST_NAMES = [
    "Alejandro", "Sofia", "Mateo", "Valentina", "Santiago", "Isabella", "Leonardo", "Camila", 
    "Matias", "Mariana", "Emilio", "Luciana", "Diego", "Victoria", "Sebastian", "Martina",
    "Nicolas", "Ximena", "Samuel", "Renata", "Daniel", "Natalia", "Carlos", "Mia", "Gabriel",
    "Valeria", "Tomas", "Fernanda", "Andres", "Julieta", "David", "Regina", "Joaquin", "Andrea",
    "Juan", "Emilia", "Felipe", "Samantha", "Eduardo", "Antonella", "Luis", "Zoe", "Fernando",
    "Paulina", "Miguel", "Ana", "Jorge", "Sara", "Pedro", "Elena"
]

LAST_NAMES = [
    "Garcia", "Martinez", "Rodriguez", "Lopez", "Hernandez", "Gonzalez", "Perez", "Sanchez",
    "Ramirez", "Torres", "Flores", "Rivera", "Gomez", "Diaz", "Reyes", "Morales", "Cruz",
    "Ortiz", "Gutierrez", "Chavez", "Ramos", "Ruiz", "Mendoza", "Alvarez", "Castillo",
    "Romero", "Jimenez", "Vasquez", "Fernandez", "Navarro", "Mendez", "Salazar", "Rojas",
    "Guzman", "Herrera", "Medina", "Aguilar", "Vargas", "Castro", "Moreno", "Munoz", "Soto",
    "Acosta", "Rios", "Silva", "Delgado", "Guerrero", "Vega", "Pena", "Maldonado"
]

# Semilla fija: garantiza que el dataset generado sea siempre el mismo
# entre corridas del script (mismo ruido, mismos nombres ficticios asignados).
SEED = 42

def calculate_mbti_scores(row):
    # E/I
    sum_e = row['q1_raw'] + row['q3_raw'] + row['q5_raw']
    sum_i = row['q2_raw'] + row['q4_raw'] + row['q6_raw']
    energia = sum_e - sum_i
    
    # S/N
    sum_s = row['q7_raw'] + row['q9_raw'] + row['q11_raw']
    sum_n = row['q8_raw'] + row['q10_raw'] + row['q12_raw']
    percepcion = sum_s - sum_n
    
    # T/F
    sum_t = row['q13_raw'] + row['q15_raw'] + row['q17_raw']
    sum_f = row['q14_raw'] + row['q16_raw'] + row['q18_raw']
    decision = sum_t - sum_f
    
    # J/P
    sum_j = row['q19_raw'] + row['q21_raw'] + row['q23_raw']
    sum_p = row['q20_raw'] + row['q22_raw'] + row['q24_raw']
    estilo = sum_j - sum_p
    
    tipo = ""
    tipo += "E" if energia >= 0 else "I"
    tipo += "S" if percepcion >= 0 else "N"
    tipo += "T" if decision >= 0 else "F"
    tipo += "J" if estilo >= 0 else "P"
    
    return pd.Series([energia, percepcion, decision, estilo, tipo])

def main():
    # Fijar la semilla ANTES de cualquier llamada aleatoria, para que
    # random.choice, random.randint y np.random.choice sean reproducibles.
    random.seed(SEED)
    np.random.seed(SEED)

    base_file = '../Cuestionario MBTI - Hoja 1.csv'
    output_file = 'datos_mbti_2k.csv'
    
    if not os.path.exists(base_file):
        print(f"Error: Base file {base_file} not found.")
        return
        
    df_base = pd.read_csv(base_file)
    print(f"Loaded {len(df_base)} original rows.")
    
    # We want 10000 rows in total: 54 original + 9946 synthetic
    total_rows = 2000
    num_synthetic = total_rows - len(df_base)
    
    # Generate exactly num_synthetic unique names
    unique_names = set()
    original_names = set(df_base['nombre'].dropna().tolist())
    
    while len(unique_names) < num_synthetic:
        # Use 2 last names to increase combinations (50 * 50 * 50 = 125,000 combinations)
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in original_names:
            unique_names.add(name)
            
    unique_names_list = list(unique_names)
    
    synthetic_rows = []
    
    # Start with the original rows exactly as they are
    for i in range(len(df_base)):
        synthetic_rows.append(df_base.iloc[i].copy())
    
    # Generate synthetic rows
    base_indices = np.random.choice(df_base.index, size=num_synthetic, replace=True)
    
    for i, idx in enumerate(base_indices):
        base_row = df_base.iloc[idx].copy()
        
        # Add slight noise to timestamp
        try:
            ts = pd.to_datetime(base_row['timestamp'])
            ts = ts + timedelta(minutes=random.randint(-10000, 10000))
            base_row['timestamp'] = ts.isoformat()
        except:
            pass
            
        # Add noise to answers
        for col_i in range(1, 25):
            col = f'q{col_i}_raw'
            val = base_row[col]
            noise = random.choice([-1, 0, 1])
            new_val = min(5, max(1, val + noise))
            base_row[col] = new_val
            
        # Assign unique generated name
        base_row['nombre'] = unique_names_list[i]
            
        synthetic_rows.append(base_row)
        
    df_synthetic = pd.DataFrame(synthetic_rows)
    
    # Recalculate scores and type
    df_synthetic[['energia_score', 'percepcion_score', 'decision_score', 'estilo_score', 'tipo_resultante']] = df_synthetic.apply(calculate_mbti_scores, axis=1)
    
    df_synthetic.to_csv(output_file, index=False)
    print(f"Generated {len(df_synthetic)} synthetic rows and saved to {output_file}")
    print(f"Seed usada: {SEED} (misma seed = mismo resultado en cualquier corrida)")

if __name__ == '__main__':
    main()