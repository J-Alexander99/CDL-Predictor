"""
Simple explainer tool to understand prediction results
Makes the black box transparent
"""
from src.predictor import EnsemblePredictor
import click


def explain_prediction(team_a: str, team_b: str):
    """Explain each prediction in plain English"""
    
    ensemble = EnsemblePredictor()
    results = ensemble.predict_all(team_a, team_b)
    
    print(f"\n{'='*80}")
    print(f"PREDICTION EXPLAINER: {team_a} vs {team_b}")
    print(f"{'='*80}\n")
    
    # Statistical Model Explanation
    print("📊 STATISTICAL MODEL (Your Original Enhanced Model)")
    print("-" * 80)
    stat = results['predictions']['statistical']
    if 'error' not in stat:
        stat_details = stat['details']
        stats_a = stat_details['team_a_stats']
        stats_b = stat_details['team_b_stats']
        
        print(f"\n{team_a}:")
        print(f"  • Win Rate: {stats_a['win_rate']:.1f}% (from {stats_a['matches_played']} matches)")
        print(f"  • Recent Form: {stats_a['momentum']:+.3f} {'🔥' if stats_a['momentum'] > 0.3 else '❄️' if stats_a['momentum'] < -0.3 else '='}")
        print(f"  • Player Quality: {stats_a['roster_quality']['avg_kd']:.2f} K/D, {stats_a['roster_quality']['avg_rating']:.2f} Rating")
        
        print(f"\n{team_b}:")
        print(f"  • Win Rate: {stats_b['win_rate']:.1f}% (from {stats_b['matches_played']} matches)")
        print(f"  • Recent Form: {stats_b['momentum']:+.3f} {'🔥' if stats_b['momentum'] > 0.3 else '❄️' if stats_b['momentum'] < -0.3 else '='}")
        print(f"  • Player Quality: {stats_b['roster_quality']['avg_kd']:.2f} K/D, {stats_b['roster_quality']['avg_rating']:.2f} Rating")
        
        print(f"\n➜ Verdict: {stat['predicted_winner']} wins {stat['team_a_probability']:.0f}%-{stat['team_b_probability']:.0f}%")
        print(f"  Why: ", end="")
        
        # Explain the statistical prediction - based on who actually won
        winner = stat['predicted_winner']
        winner_is_a = (winner == team_a)
        
        # Get the actual winner's stats
        if winner_is_a:
            winner_stats = stats_a
            loser_stats = stats_b
            loser_name = team_b
        else:
            winner_stats = stats_b
            loser_stats = stats_a
            loser_name = team_a
        
        # Explain why they won
        if winner_stats['momentum'] > loser_stats['momentum'] + 0.3:
            print(f"{winner} is much hotter right now (momentum: {winner_stats['momentum']:.2f} vs {loser_stats['momentum']:.2f})")
        elif winner_stats['win_rate'] > loser_stats['win_rate'] + 10:
            print(f"{winner} has better win rate ({winner_stats['win_rate']:.0f}% vs {loser_stats['win_rate']:.0f}%)")
        elif winner_stats['roster_quality']['avg_rating'] > loser_stats['roster_quality']['avg_rating'] + 0.05:
            print(f"{winner} has better player quality (rating: {winner_stats['roster_quality']['avg_rating']:.2f} vs {loser_stats['roster_quality']['avg_rating']:.2f})")
        elif stat['team_a_probability'] > 45 and stat['team_a_probability'] < 55:
            print("Very close matchup - essentially a toss-up")
        else:
            print("Small advantages in multiple factors add up")
    
    # Elo Model Explanation
    print(f"\n\n⚖️  ELO RATING SYSTEM (Like Chess/League Rankings)")
    print("-" * 80)
    elo = results['predictions']['elo']
    if 'error' not in elo:
        rating_diff = elo['team_a_rating'] - elo['team_b_rating']
        
        print(f"\n{team_a}: {elo['team_a_rating']:.0f} Elo (from {elo['details']['team_a_matches']} rated matches)")
        print(f"{team_b}: {elo['team_b_rating']:.0f} Elo (from {elo['details']['team_b_matches']} rated matches)")
        print(f"Rating Difference: {abs(rating_diff):.0f} points")
        
        print(f"\n➜ Verdict: {elo['predicted_winner']} wins {elo['team_a_probability']:.0f}%-{elo['team_b_probability']:.0f}%")
        print(f"  Why: ", end="")
        
        if abs(rating_diff) < 20:
            print("Teams are evenly matched (similar rating)")
        elif rating_diff > 50:
            print(f"{team_a} is significantly higher rated (+{rating_diff:.0f} points)")
        elif rating_diff < -50:
            print(f"{team_b} is significantly higher rated (+{abs(rating_diff):.0f} points)")
        else:
            winner_name = team_a if rating_diff > 0 else team_b
            print(f"{winner_name} has slight rating advantage ({abs(rating_diff):.0f} points)")
    
    # ML Model Explanation
    print(f"\n\n🤖 MACHINE LEARNING MODEL (Learned from 82 matches)")
    print("-" * 80)
    ml = results['predictions']['ml']
    if 'error' not in ml:
        ml_details = ml['details']
        h2h = ml_details['head_to_head']
        
        print(f"\nKey Factors the ML Model Weighs Most:")
        if h2h['total_matches'] > 0:
            h2h_winner = team_a if h2h['team_a_wins'] > h2h['team_b_wins'] else team_b
            print(f"  1. Head-to-Head History: {team_a} {h2h['team_a_wins']}-{h2h['team_b_wins']} {team_b}")
            print(f"     → ML learned this is THE most important factor (weight: +2.66)")
        else:
            print(f"  1. No head-to-head history")
        
        print(f"  2. Momentum: {team_a} {stats_a['momentum']:+.2f} vs {team_b} {stats_b['momentum']:+.2f}")
        print(f"  3. Player Ratings: {stats_a['roster_quality']['avg_rating']:.2f} vs {stats_b['roster_quality']['avg_rating']:.2f}")
        
        print(f"\n➜ Verdict: {ml['predicted_winner']} wins {ml['team_a_probability']:.0f}%-{ml['team_b_probability']:.0f}%")
        print(f"  Why: ", end="")
        
        if h2h['total_matches'] > 0:
            if h2h['team_a_wins'] > h2h['team_b_wins'] * 1.5:
                print(f"{team_a} dominates the H2H history ({h2h['team_a_wins']}-{h2h['team_b_wins']})")
            elif h2h['team_b_wins'] > h2h['team_a_wins'] * 1.5:
                print(f"{team_b} dominates the H2H history ({h2h['team_b_wins']}-{h2h['team_a_wins']})")
            else:
                print(f"H2H is close, ML considers other factors")
        else:
            print("No H2H history, ML uses momentum + player quality")
    
    # Ensemble Explanation
    print(f"\n\n🎯 ENSEMBLE (FINAL PREDICTION)")
    print("=" * 80)
    ens = results['ensemble']
    if 'error' not in ens:
        print(f"\nHow it works: Weighted average of all three models")
        print(f"  • Statistical Model: 40% weight")
        print(f"  • Elo Rating: 35% weight")
        print(f"  • Machine Learning: 25% weight")
        
        print(f"\n➜ FINAL VERDICT: {ens['predicted_winner']} wins {ens['predicted_score']}")
        print(f"   Probability: {ens['team_a_probability']:.1f}% vs {ens['team_b_probability']:.1f}%")
        print(f"   Confidence: {ens['confidence']:.1f}%")
        
        if ens['models_agree']:
            print(f"   ✓ All three models agree - HIGH CONFIDENCE")
        else:
            print(f"   ⚠ Models disagree - LOWER CONFIDENCE")
            print(f"\n   What each model says:")
            if 'error' not in stat:
                print(f"     Statistical: {stat['predicted_winner']}")
            if 'error' not in elo:
                print(f"     Elo Rating: {elo['predicted_winner']}")
            if 'error' not in ml:
                print(f"     ML Model: {ml['predicted_winner']}")
    
    print(f"\n{'='*80}")
    print("BOTTOM LINE:")
    print("-" * 80)
    print(f"Prediction: {ens['predicted_winner']} is favored to win")
    print(f"Score: {ens['predicted_score']}")
    print(f"Confidence: {'HIGH' if ens['confidence'] > 30 else 'MODERATE' if ens['confidence'] > 15 else 'LOW'}")
    
    # Recommend which model to trust
    if ens['models_agree']:
        print(f"Recommendation: Trust the ensemble - all models agree")
    else:
        print(f"\nModels disagree - here's which to trust:")
        if h2h['total_matches'] >= 3:
            print(f"  → Trust ML MODEL (they've played {h2h['total_matches']} times before)")
        elif abs(rating_diff) > 50:
            print(f"  → Trust ELO RATING (clear skill difference)")
        else:
            print(f"  → Trust STATISTICAL MODEL (best for close matchups)")
    
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python explain_prediction.py 'Team A' 'Team B'")
        sys.exit(1)
    
    explain_prediction(sys.argv[1], sys.argv[2])
