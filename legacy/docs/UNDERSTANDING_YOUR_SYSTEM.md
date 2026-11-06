# Understanding Your Prediction System (Plain English)

## The Problem You Had
Your system became too complex. Three different models making predictions, and you don't know which one to trust or why they're saying different things.

## Simple Solution: Use the Explainer

Instead of `python main.py compare-predictions`, use:

```bash
python explain_prediction.py "Team A" "Team B"
```

This shows you **in plain English** what each model is thinking and WHY.

---

## Your Three Models (Simplified)

### 1. 📊 Statistical Model (Your Original, Enhanced)
**What it does:** Looks at recent performance, win rates, player stats, momentum

**Best for:**
- Teams you've never seen play each other
- When you want to know "who's hot right now?"
- General matchups

**Weaknesses:**
- Doesn't learn from past matchups
- Can be fooled by teams that got lucky recently

**Think of it like:** Looking at a boxer's recent record and training stats

---

### 2. ⚖️ Elo Rating (Like Chess Rankings)
**What it does:** Gives each team a number (1500 = average). Teams gain/lose points when they win/lose

**Best for:**
- Overall "power rankings"
- When teams haven't played each other
- Quick skill comparison

**Weaknesses:**
- Doesn't adapt to momentum or roster changes quickly
- Treats all wins equally (beating a great team = beating a bad team)

**Think of it like:** A boxing ranking - who's #1, #2, #3?

---

### 3. 🤖 Machine Learning Model
**What it does:** Looked at 82 historical matches and learned "what factors actually matter for winning"

**Best for:**
- Teams with head-to-head history (H2H)
- It learned that H2H matters MOST (+2.66 weight)
- Finding hidden patterns

**Weaknesses:**
- Only trained on 82 matches (not a lot of data)
- Can be overconfident when teams have H2H history
- Black box (hardest to understand)

**Think of it like:** A sports bettor who memorized every past fight

---

## Which Model Should I Trust?

### Use this decision tree:

1. **Have the teams played 3+ times before?**
   - YES → Trust **ML Model** (it weighs H2H history heavily)
   - NO → Go to step 2

2. **Is one team rated 50+ Elo points higher?**
   - YES → Trust **Elo Rating** (clear skill gap)
   - NO → Go to step 3

3. **Is one team on a hot/cold streak?**
   - YES → Trust **Statistical Model** (best at catching momentum)
   - NO → Trust **Ensemble** (let all three vote)

---

## The Ensemble: Your "Committee Decision"

The ensemble combines all three:
- 40% Statistical (your enhanced model)
- 35% Elo (skill rating)
- 25% ML (learned patterns)

**When it's confident:** All three models agree ✓
**When it's uncertain:** Models disagree ⚠

---

## Quick Start: Just Run This

```bash
# See everything explained in plain English
python explain_prediction.py "OpTic Texas" "FaZe Vegas"
```

It will tell you:
1. What each model says
2. WHY each model thinks that
3. Which model to trust
4. Final recommendation

---

## Going Back to Basics

If this is still too much, you can use JUST the statistical model (your original enhanced one):

```bash
python main.py predict --team-a "Team A" --team-b "Team B"
```

This ignores Elo and ML entirely. Just uses win rates, momentum, player stats, and H2H.

---

## When Should I Retrain the Models?

**After scraping new matches:**

```bash
# Step 1: Update Elo ratings with new match results
python main.py init-elo --force

# Step 2: Retrain ML model on expanded dataset
python main.py train-ml
```

Do this every 10-20 new matches to keep models fresh.

---

## The Bottom Line

1. **Most of the time:** Use the ensemble (it's smart)
2. **When confused:** Run `explain_prediction.py` to see what's happening
3. **When in doubt:** Fall back to statistical model only (`predict` command)
4. **For specific cases:** Use the decision tree above

Your system isn't broken - it's just powerful. The explainer will make it transparent.
