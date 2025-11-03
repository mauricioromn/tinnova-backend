import os
import json
import math
import argparse
import pandas as pd
from joblib import dump, load
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error

DATA_CSV = os.path.join(os.getcwd(), "historico_cotizaciones.csv")
MODEL_DIR = os.path.join(os.getcwd(), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "precio_unitario.joblib")
META_PATH = os.path.join(MODEL_DIR, "meta.json")

def load_data(csv_path=DATA_CSV):
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["descripcion", "cantidad", "precio_unitario"])
    df = df[(df["precio_unitario"] > 0) & (df["precio_unitario"] < 500)]
    df = df[(df["cantidad"] > 0) & (df["cantidad"] < 10000)]
    df["texto"] = (df["empresa"].fillna("") + " " + df["descripcion"].fillna("")).str.lower()
    return df

def build_pipeline():
    preproc = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(ngram_range=(1,2), min_df=2), "texto"),
            ("num", "passthrough", ["cantidad"]),
        ]
    )
    model = Ridge(alpha=1.0, random_state=42)
    return Pipeline([("preproc", preproc), ("reg", model)])

def train():
    os.makedirs(MODEL_DIR, exist_ok=True)
    df = load_data()
    X = df[["texto", "cantidad"]]
    y = df["precio_unitario"]

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    pipe = build_pipeline()
    pipe.fit(Xtr, ytr)
    pred = pipe.predict(Xte)
    rmse = math.sqrt(mean_squared_error(yte, pred))

    dump(pipe, MODEL_PATH)
    with open(META_PATH, "w") as f:
        json.dump({"rmse": rmse, "n_rows": len(df)}, f, indent=2)

    print(f"✅ Entrenado con {len(df)} filas. RMSE: {rmse:.2f}")

def predict(empresa, descripcion, cantidad):
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Modelo no entrenado aún.")
    pipe = load(MODEL_PATH)
    meta = json.load(open(META_PATH))
    rmse = meta.get("rmse", 5)
    texto = f"{empresa} {descripcion}".lower()
    X = pd.DataFrame([{"texto": texto, "cantidad": cantidad}])
    pu = float(pipe.predict(X)[0])
    pu = max(pu, 0.1)
    total = pu * cantidad
    return {
        "precio_unitario_estimado": round(pu, 2),
        "margen_inferior": round(max(pu - rmse, 0.1), 2),
        "margen_superior": round(pu + rmse, 2),
        "total_estimado": round(total, 2),
        "rmse": round(rmse, 2),
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--predict", action="store_true")
    ap.add_argument("--empresa", type=str, default="")
    ap.add_argument("--descripcion", type=str, default="")
    ap.add_argument("--cantidad", type=int, default=1)
    args = ap.parse_args()

    if args.train:
        train()
    elif args.predict:
        print(predict(args.empresa, args.descripcion, args.cantidad))

