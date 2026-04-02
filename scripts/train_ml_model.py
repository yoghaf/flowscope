import asyncio
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import sys

# Inject root directory into python path to allow absolute imports from 'backend'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import Settings
from backend.database import DatabaseManager

async def main():
    settings = Settings()
    db = DatabaseManager(settings)
    await db.initialize()
    
    print("Fetching historical trades from Database...")
    trades = await db.list_trade_signals()
    
    data = []
    for t in trades:
        # Only use trades that are closed (either 'win' or 'loss')
        if t.result in ["win", "loss"] and t.entry_features:
            feat = dict(t.entry_features)
            
            # The target label: 1 for Win, 0 for Loss
            feat["_label"] = 1 if t.result == "win" else 0
            
            # Remove non-numerical metadata if it exists
            feat.pop("insights", None)
            
            data.append(feat)
            
    if not data:
        print("No training data available. Run the replay script or collect live trades first.")
        await db.close()
        return
        
    df = pd.DataFrame(data)
    
    # Fill NAs with 0 (e.g. if some features weren't available at that timestamp)
    df.fillna(0, inplace=True)
    
    # Filter to only numeric features
    X = df.drop(columns=["_label"]).select_dtypes(include=["number"])
    y = df["_label"]
    
    print(f"Training ML Model on {len(df)} trade samples with {X.shape[1]} metrics (features)...")
    
    # Split into Train and Validation sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # We use Random Forest because it naturally handles non-linear bounds like 'ATR > 0.06'
    model = RandomForestClassifier(n_estimators=100, max_depth=7, random_state=42, class_weight="balanced")
    model.fit(X_train, y_train)
    
    preds = model.predict(X_test)
    print("\n================ MODEL PERFORMANCE ==================")
    print("Accuracy:", accuracy_score(y_test, preds))
    print(classification_report(y_test, preds))
    print("=====================================================")
    
    # Analyze Feature Importances
    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\nTop 10 Most Important Features predicting Win/Loss:")
    print(importances.head(10))
    
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/rf_model.pkl")
    print("\n✅ Model saved successfully to models/rf_model.pkl")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
