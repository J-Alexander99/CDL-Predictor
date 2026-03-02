# CDL Predictor - Three-Model System Guide

## Overview

Your CDL Predictor now has **three different prediction models** that you can use individually or combined:

1. **Statistical Model** - Your original model with roster weighting, momentum, mode-specific stats
2. **Elo Rating System** - Dynamic ratings that update after each match
3. **Machine Learning Model** - Learns optimal feature weights from historical data

## Setup

### Prerequisites
```bash
pip install scikit-learn>=1.3.0
```

### Initialize the Systems

**1. Initialize Elo Ratings:**
```bash
python main.py init-elo
```
This processes all matches chronologically and assigns Elo ratings to each team-roster combination.

**2. Train ML Model:**
```bash
python main.py train-ml
```
This trains a logistic regression model on historical matchdata to learn which features matter most.

## Usage

### Compare All Three Models
```bash
python main.py compare-predictions --team-a "OpTic Texas" --team-b "FaZe Vegas"
```

Shows predictions from all three models side-by-side plus an ensemble prediction.

### Use Individual Models
```bash
# Statistical model (your original)
python main.py predict --team-a "Team A" --team-b "Team B"

# Elo model only
python -c "from src.predictor import EloPredictor; elo = EloPredictor(); print(elo.predict('Team A', 'Team B'))"

# ML model only  
python -c "from src.predictor import MLPredictor; ml = MLPredictor(); print(ml.predict('Team A', 'Team B'))"
```

## How Each Model Works

### 1. Statistical Model (Enhanced from Original)
**Strengths:**
- Mode-specific predictions (Hardpoint, S&D, Overload)
- Map-by-map breakdown
- Map pool prediction
- Roster-weighted history
- Time-decay (recent matches matter more)
- Momentum calculation

**Best for:** Understanding *why* a prediction was made, mode-specific insights

**Weight in Ensemble:** 40%

### 2. Elo Rating System
**Strengths:**
- Self-calibrating (improves over time)
- Simple and robust
- Handles roster changes naturally
- Updates after each match

**How it works:**
- Each team-roster starts at 1500 rating
- Win against higher-rated team = big rating gain
- Win against lower-rated team = small rating gain
- Ratings transferred partially when roster changes

**Best for:** Quick overall team strength assessment

**Weight in Ensemble:** 35%

### 3. Machine Learning Model
**Strengths:**
- Learns from data (no manual tuning)
- Finds non-obvious patterns
- Can weight any feature

**Current Training Results:**
- Training accuracy: 89%
- Most important features:
  1. Head-to-head history (+2.66)
  2. Momentum (+0.18)
  3. Rating differential (+0.17)

**Best for:** Pure accuracy when enough data exists

**Weight in Ensemble:** 25%

## Maintenance

### After Scraping New Matches

**Option 1: Automatic (Recommended)**
Add to your scraping workflow:
```python
from src.predictor import EloPredictor

# After match is scraped and saved to database
elo = EloPredictor()
elo.update_ratings(team_a, roster_a, team_b, roster_b, score_a, score_b, match_date)
```

**Option 2: Manual Re-initialization**
```bash
python main.py init-elo --force      # Recalculate all Elo ratings
python main.py train-ml              # Retrain ML model
```

### Tuning Ensemble Weights

Edit `src/predictor/ensemble_predictor.py`:
```python
weights = {
    'statistical': 0.40,  # Adjust these based on accuracy
    'elo': 0.35,
    'ml': 0.25
}
```

## Example Output Analysis

```
PREDICTION COMPARISON: OpTic Texas vs FaZe Vegas

Statistical Model:
  OpTic Texas: 51.3%      ← Slightly favors OpTic
  FaZe Vegas: 48.7%
  Winner: FaZe Vegas (3-1)

Elo Rating System:
  OpTic Texas: 54.0%      ← Favors OpTic more strongly
  FaZe Vegas: 46.0%
  OpTic Rating: 1575.6    ← Higher Elo rating
  FaZe Rating: 1547.8

Machine Learning:
  OpTic Texas: 4.6%       ← ML strongly disagrees!
  FaZe Vegas: 95.4%       ← Sees something others don't
  Winner: FaZe Vegas (0-3)

ENSEMBLE:
  OpTic Texas: 40.6%
  FaZe Vegas: 59.4%       ← Combined prediction
  Agreement: ⚠ Models disagree
```

**Interpretation:**
- Statistical & Elo think it's close
- ML model sees FaZe as heavy favorite (likely due to H2H history having huge weight)
- When models disagree, confidence is lower
- Ensemble averages them based on weights

## Advanced Usage

### Backtest Predictions
Track accuracy over time:
```python
# Save predictions before match
# After match, compare prediction to actual result
# Calculate accuracy for each model
```

### Custom Ensemble
Create your own ensemble with different weights:
```python
from src.predictor import EnsemblePredictor

ensemble = EnsemblePredictor()
results = ensemble.predict_all(team_a, team_b)

# Custom weights
custom_weights = {
    'statistical': 0.50,  # Trust your model more
    'elo': 0.30,
    'ml': 0.20
}
custom_ensemble = ensemble._calculate_ensemble(results['predictions'], custom_weights)
```

## Troubleshooting

**"ML model not trained"**
```bash
python main.py train-ml
```

**"Elo ratings not initialized"**
```bash
python main.py init-elo
```

**"Insufficient training data"**
- Need at least 20 matches with full roster data
- Scrape more matches first

**ML gives extreme predictions (0% or 100%)**
- May indicate overfitting
- Retrain with more data
- Reduce importance of H2H feature

## Next Steps

1. **Track Accuracy**: Keep a log of predictions vs actual results
2. **Tune Weights**: Adjust ensemble weights based on which model is most accurate
3. **Add More Features**: The ML model can incorporate ANY stat you have
4. **Implement Map-Specific Elo**: Track Elo per mode/map for even better accuracy

---

**Pro Tip:** Use `compare-predictions` for important matches to see all perspectives. Use the model that aligns best with your understanding of the matchup as a tiebreaker when models disagree!
