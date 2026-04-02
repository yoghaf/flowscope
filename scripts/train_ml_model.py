import asyncio
import glob
import os
import sys

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Inject root directory into python path to allow absolute imports from 'backend'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import Settings
from backend.database import DatabaseManager


def _load_csv_data(csv_dir: str) -> list[dict]:
    """Load trade data from ALL replay CSV files in the given directory."""
    data: list[dict] = []
    pattern = os.path.join(csv_dir, "replay-performance-report*.csv")
    csv_files = sorted(glob.glob(pattern))

    if not csv_files:
        return data

    print(f"Found {len(csv_files)} replay CSV file(s):")
    for f in csv_files:
        print(f"  📄 {os.path.basename(f)}")

    frames = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            if "result" in df.columns:
                frames.append(df)
        except Exception as e:
            print(f"  ⚠️  Skipping {os.path.basename(csv_path)}: {e}")

    if not frames:
        return data

    combined = pd.concat(frames, ignore_index=True)
    valid_df = combined[combined["result"].isin(["win", "loss"])]

    feat_cols = [c for c in valid_df.columns if c.startswith("feat_")]
    if not feat_cols:
        print("  ⚠️  No feature columns (feat_*) found in CSV files.")
        return data

    for _, row in valid_df.iterrows():
        feat = {c.replace("feat_", ""): row[c] for c in feat_cols if pd.notnull(row[c])}
        feat["_label"] = 1 if row["result"] == "win" else 0
        data.append(feat)

    return data


async def main():
    settings = Settings()
    db = DatabaseManager(settings)
    await db.init()

    # ── Step 1: Try loading from live DB first ──────────────────────
    print("=" * 60)
    print("  FLOWSCOPE ML TRAINING PIPELINE")
    print("=" * 60)
    print("\n[1/4] Fetching historical trades from Database...")
    trades = await db.list_trade_signals()

    data: list[dict] = []
    for t in trades:
        if t.result in ["win", "loss"] and t.entry_features:
            feat = dict(t.entry_features)
            feat["_label"] = 1 if t.result == "win" else 0
            feat.pop("insights", None)
            data.append(feat)

    if data:
        print(f"  ✅ Loaded {len(data)} trades from live DB.")
    else:
        print("  ⚠️  No live trades in DB.")

    # ── Step 2: Augment with ALL replay CSV files ───────────────────
    print("\n[2/4] Scanning for replay CSV data...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_data = _load_csv_data(project_root)
    if csv_data:
        data.extend(csv_data)
        print(f"  ✅ Loaded {len(csv_data)} trades from replay CSVs.")
    else:
        print("  ⚠️  No replay CSV data found.")

    # ── Deduplicate ─────────────────────────────────────────────────
    before = len(data)
    df = pd.DataFrame(data)
    df.fillna(0, inplace=True)
    df.drop_duplicates(inplace=True)
    print(f"  📊 Total unique samples: {len(df)} (deduped from {before})")

    if len(df) < 10:
        print("\n❌ Not enough data to train a meaningful model (need >= 10 samples).")
        await db.close()
        return

    # ── Step 3: Train ───────────────────────────────────────────────
    X = df.drop(columns=["_label"]).select_dtypes(include=["number"])
    y = df["_label"]

    print(f"\n[3/4] Training Random Forest on {len(df)} samples × {X.shape[1]} features...")

    # Stratified split (preserve win/loss ratio in both sets)
    test_size = 0.2 if len(df) >= 30 else 0.3
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=5,
        min_samples_leaf=3,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    # Cross-validation for more robust accuracy estimate
    cv_folds = min(5, len(df) // 5) if len(df) >= 25 else 3
    cv_scores = cross_val_score(model, X, y, cv=cv_folds, scoring="accuracy")

    preds = model.predict(X_test)

    print("\n" + "=" * 60)
    print("  MODEL PERFORMANCE")
    print("=" * 60)
    print(f"  Hold-out Accuracy : {accuracy_score(y_test, preds):.2%}")
    print(f"  Cross-Val Accuracy: {cv_scores.mean():.2%} (±{cv_scores.std():.2%})")
    print(f"  Train size: {len(X_train)} | Test size: {len(X_test)}")
    print()
    print(classification_report(y_test, preds, target_names=["Loss", "Win"], zero_division=0))
    print("=" * 60)

    # ── Step 4: Feature Importances ─────────────────────────────────
    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\n[4/4] Top 15 Most Important Features (Win/Loss Predictors):")
    print("-" * 50)
    for i, (feat, score) in enumerate(importances.head(15).items(), 1):
        bar = "█" * int(score * 100)
        print(f"  {i:>2}. {feat:<35s} {score:.4f}  {bar}")

    # Save model
    os.makedirs("models", exist_ok=True)
    model_path = os.path.join("models", "rf_model.pkl")
    joblib.dump(model, model_path)
    print(f"\n✅ Model saved to {model_path}")
    print(f"   Features: {X.shape[1]} | Samples: {len(df)} | CV Accuracy: {cv_scores.mean():.2%}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
