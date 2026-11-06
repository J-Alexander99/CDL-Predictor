"""
Simple decision helper - tells you which model to trust
"""
from src.predictor import EnsemblePredictor
import sys


def which_model(team_a: str, team_b: str):
    """Tell the user which model to trust for this matchup"""
    
    ensemble = EnsemblePredictor()
    results = ensemble.predict_all(team_a, team_b)
    
    print(f"\n{'='*60}")
    print(f"WHICH MODEL SHOULD I TRUST?")
    print(f"{team_a} vs {team_b}")
    print(f"{'='*60}\n")
    
    # Get key metrics
    stat = results['predictions']['statistical']
    elo = results['predictions']['elo']
    ml = results['predictions']['ml']
    
    # Get H2H info
    if 'error' not in ml:
        h2h = ml['details']['head_to_head']
        h2h_matches = h2h['total_matches']
    else:
        h2h_matches = 0
    
    # Get rating difference
    if 'error' not in elo:
        rating_diff = abs(elo['team_a_rating'] - elo['team_b_rating'])
    else:
        rating_diff = 0
    
    # Get momentum difference
    if 'error' not in stat:
        stats_a = stat['details']['team_a_stats']
        stats_b = stat['details']['team_b_stats']
        momentum_diff = abs(stats_a['momentum'] - stats_b['momentum'])
    else:
        momentum_diff = 0
    
    # Decision tree
    recommendation = None
    reason = ""
    
    # Check H2H first
    if h2h_matches >= 3:
        recommendation = "ML MODEL"
        reason = f"They've played {h2h_matches} times before. The ML model learned that head-to-head history is THE most important factor (weight: +2.66). When teams have history together, past results predict future results."
    
    # Check rating gap
    elif rating_diff > 50:
        recommendation = "ELO RATING"
        reason = f"There's a {rating_diff:.0f} point Elo gap - that's significant. Elo is best at identifying clear skill differences between teams. The better-rated team should win."
    
    # Check momentum
    elif momentum_diff > 0.5:
        recommendation = "STATISTICAL MODEL"
        hot_team = team_a if stats_a['momentum'] > stats_b['momentum'] else team_b
        reason = f"{hot_team} has much stronger momentum right now (difference: {momentum_diff:.2f}). The statistical model is best at catching teams riding hot/cold streaks. Form matters."
    
    # Close matchup
    else:
        recommendation = "ENSEMBLE (all three)"
        reason = "This is a close matchup with no clear advantages. Let all three models vote and use their weighted average. The ensemble is smartest when there's uncertainty."
    
    # Print recommendation
    print(f"✅ RECOMMENDATION: {recommendation}")
    print(f"\n{reason}\n")
    
    # Show what that model says
    print(f"{'='*60}")
    print(f"WHAT {recommendation} SAYS:")
    print(f"{'='*60}\n")
    
    if recommendation == "ML MODEL" and 'error' not in ml:
        print(f"Winner: {ml['predicted_winner']}")
        print(f"Probability: {ml['team_a_probability']:.0f}% vs {ml['team_b_probability']:.0f}%")
        print(f"H2H Record: {team_a} {h2h['team_a_wins']}-{h2h['team_b_wins']} {team_b}")
    
    elif recommendation == "ELO RATING" and 'error' not in elo:
        print(f"Winner: {elo['predicted_winner']}")
        print(f"Probability: {elo['team_a_probability']:.0f}% vs {elo['team_b_probability']:.0f}%")
        print(f"Ratings: {team_a} {elo['team_a_rating']:.0f} vs {team_b} {elo['team_b_rating']:.0f}")
    
    elif recommendation == "STATISTICAL MODEL" and 'error' not in stat:
        print(f"Winner: {stat['predicted_winner']}")
        print(f"Probability: {stat['team_a_probability']:.0f}% vs {stat['team_b_probability']:.0f}%")
        print(f"Momentum: {team_a} {stats_a['momentum']:+.2f} 🔥 vs {team_b} {stats_b['momentum']:+.2f}")
    
    else:  # Ensemble
        ens = results['ensemble']
        print(f"Winner: {ens['predicted_winner']}")
        print(f"Probability: {ens['team_a_probability']:.0f}% vs {ens['team_b_probability']:.0f}%")
        print(f"Confidence: {ens['confidence']:.1f}%")
        print(f"Score: {ens['predicted_score']}")
        
        if ens['models_agree']:
            print("\n✓ All three models agree!")
        else:
            print("\n⚠ Models disagree:")
            if 'error' not in stat:
                print(f"  Statistical: {stat['predicted_winner']}")
            if 'error' not in elo:
                print(f"  Elo: {elo['predicted_winner']}")
            if 'error' not in ml:
                print(f"  ML: {ml['predicted_winner']}")
    
    print(f"\n{'='*60}")
    print(f"Need more details? Run:")
    print(f"  python explain_prediction.py \"{team_a}\" \"{team_b}\"")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python which_model.py 'Team A' 'Team B'")
        sys.exit(1)
    
    which_model(sys.argv[1], sys.argv[2])
