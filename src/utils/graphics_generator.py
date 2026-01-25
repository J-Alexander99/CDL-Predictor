"""
Generate graphics for match predictions
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path
from datetime import datetime
from PIL import Image


class PredictionGraphics:
    """Generate visual graphics for match predictions"""
    
    def __init__(self, output_dir='outputs'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.project_root = Path(__file__).parent.parent.parent
        self.images_dir = self.project_root / 'images'
        
        # Team brand colors
        self.team_colors = {
            'FaZe Vegas': '#ff01ff',  # Crimson Red
            'Vancouver Surge': '#081631',  # Teal
            'OpTic Texas': "#93c852",  # Bright Green
            'Los Angeles Thieves': '#ff0000',  # Purple
            'Miami Heretics': '#ff6e16',  # Hot Pink
            'Carolina Royal Ravens': '#0184c3',  # Royal Blue
            'Boston Breach': '#02ff5b',  # Dark Orange
            'Cloud9 New York': "#00aeee",  # Deep Sky Blue
            'Paris Gentle Mates': '#eea9e9',  # Gold
            'Toronto KOI': "#782cf3",  # Tomato/Orange-Red
            'G2 Minnesota': "#342565",  # Dodger Blue
            'Riyadh Falcons': "#1a825a",  # Gold
        }
        
        # Color scheme
        self.colors = {
            'team_a': '#FF6B6B',  # Default, will be overridden
            'team_b': '#4ECDC4',  # Default, will be overridden
            'background': '#2a2a2a',
            'text': '#eee',
            'grid': '#444',
            'accent': '#FFD93D'
        }
        
    def generate_prediction_graphic(self, prediction_data: dict, filename: str = None) -> str:
        """
        Generate complete prediction graphic
        
        Args:
            prediction_data: Dictionary with prediction results
            filename: Optional custom filename
        
        Returns:
            Path to saved graphic
        """
        # Set team-specific colors
        team_a = prediction_data['team_a']
        team_b = prediction_data['team_b']
        self.colors['team_a'] = self.team_colors.get(team_a, '#FF6B6B')
        self.colors['team_b'] = self.team_colors.get(team_b, '#4ECDC4')
        
        # Set dark background style
        plt.style.use('dark_background')
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 10), facecolor=self.colors['background'])
        
        # Create grid layout
        gs = fig.add_gridspec(4, 3, hspace=0.4, wspace=0.3, 
                             left=0.08, right=0.92, top=0.88, bottom=0.08)
        
        # Add team logos as background
        self._add_team_logos(fig, prediction_data)
        
        # Title
        self._add_title(fig, prediction_data)
        
        # Main win probability (large)
        ax_prob = fig.add_subplot(gs[0:2, 0:2])
        self._plot_win_probability(ax_prob, prediction_data)
        
        # Predicted score
        ax_score = fig.add_subplot(gs[0, 2])
        self._plot_predicted_score(ax_score, prediction_data)
        
        # Confidence meter
        ax_conf = fig.add_subplot(gs[1, 2])
        self._plot_confidence(ax_conf, prediction_data)
        
        # Stats comparison (left third)
        ax_stats = fig.add_subplot(gs[2, 0])
        self._plot_stats_comparison(ax_stats, prediction_data)
        
        # Pick/Ban predictions (right two-thirds)
        ax_pickban = fig.add_subplot(gs[2, 1:])
        self._plot_pickban_prediction(ax_pickban, prediction_data)
        
        # Mode breakdown
        ax_modes = fig.add_subplot(gs[3, :])
        self._plot_mode_breakdown(ax_modes, prediction_data)
        
        # Generate filename
        if not filename:
            team_a = prediction_data['team_a'].replace(' ', '')
            team_b = prediction_data['team_b'].replace(' ', '')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{team_a}_vs_{team_b}_{timestamp}.png"
        
        # Save
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, facecolor=self.colors['background'], 
                   edgecolor='none', bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _get_team_logo_path(self, team_name: str) -> Path:
        """Find the logo file for a team"""
        # Clean team name for filename matching
        clean_name = team_name.replace(' ', '')
        
        # Try different extensions
        for ext in ['.png', '.webp']:
            logo_path = self.images_dir / f"{clean_name}{ext}"
            if logo_path.exists():
                return logo_path
        
        return None
    
    def _add_team_logos(self, fig, data):
        """Add team logos as background watermarks"""
        team_a = data['team_a']
        team_b = data['team_b']
        
        # Get logo paths
        logo_a_path = self._get_team_logo_path(team_a)
        logo_b_path = self._get_team_logo_path(team_b)
        
        # Team A logo (left side)
        if logo_a_path:
            try:
                img_a = Image.open(logo_a_path)
                # Add logo to figure - positioned on left, half off screen
                ax_logo_a = fig.add_axes([-0.15, 0.25, 0.5, 0.5])
                ax_logo_a.imshow(img_a, alpha=0.15)
                ax_logo_a.axis('off')
            except Exception as e:
                pass  # Silently fail if logo can't be loaded
        
        # Team B logo (right side)
        if logo_b_path:
            try:
                img_b = Image.open(logo_b_path)
                # Add logo to figure - positioned on right, half off screen
                ax_logo_b = fig.add_axes([0.65, 0.25, 0.5, 0.5])
                ax_logo_b.imshow(img_b, alpha=0.15)
                ax_logo_b.axis('off')
            except Exception as e:
                pass  # Silently fail if logo can't be loaded
    
    def _add_title(self, fig, data):
        """Add main title to figure"""
        team_a = data['team_a']
        team_b = data['team_b']
        
        fig.text(0.5, 0.96, f"{team_a} vs {team_b}", 
                ha='center', va='top', fontsize=22, fontweight='bold',
                color=self.colors['text'])
        fig.text(0.5, 0.93, "CDL Match Prediction", 
                ha='center', va='top', fontsize=12, 
                color=self.colors['text'], alpha=0.7)
    
    def _plot_win_probability(self, ax, data):
        """Plot win probability comparison"""
        prob_a = data['team_a_win_probability']
        prob_b = data['team_b_win_probability']
        
        # Horizontal bar chart
        teams = [data['team_a'], data['team_b']]
        probs = [prob_a, prob_b]
        colors = [self.colors['team_a'], self.colors['team_b']]
        
        y_pos = [0, 1]
        bars = ax.barh(y_pos, probs, color=colors, alpha=0.8, height=0.6)
        
        # Add percentage labels
        for i, (bar, prob) in enumerate(zip(bars, probs)):
            ax.text(prob/2, i, f"{prob:.1f}%", 
                   ha='center', va='center', fontsize=20, fontweight='bold',
                   color='white')
        
        # Formatting
        ax.set_yticks(y_pos)
        ax.set_yticklabels(teams, fontsize=14, fontweight='bold')
        ax.set_xlim(0, 100)
        ax.set_xlabel('Win Probability (%)', fontsize=12, color=self.colors['text'])
        ax.set_title('WIN PROBABILITY', fontsize=16, fontweight='bold', 
                    pad=20, color=self.colors['accent'])
        ax.grid(axis='x', alpha=0.2, color=self.colors['grid'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.patch.set_alpha(0)  # Transparent background
        
        # Add 50% reference line
        ax.axvline(50, color=self.colors['text'], linestyle='--', 
                  alpha=0.3, linewidth=1)
    
    def _plot_predicted_score(self, ax, data):
        """Plot predicted match score"""
        predicted_score = data.get('predicted_score', 'N/A')
        winner = data['predicted_winner']
        
        ax.text(0.5, 0.6, predicted_score, 
               ha='center', va='center', fontsize=36, fontweight='bold',
               color=self.colors['accent'])
        ax.text(0.5, 0.3, 'Predicted Score', 
               ha='center', va='center', fontsize=12,
               color=self.colors['text'], alpha=0.7)
        ax.text(0.5, 0.1, f"Winner: {winner}", 
               ha='center', va='center', fontsize=10,
               color=self.colors['accent'], fontweight='bold')
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
    
    def _plot_confidence(self, ax, data):
        """Plot prediction confidence meter"""
        confidence = data.get('confidence', 0)  # Already a percentage (0-100)
        
        # Determine confidence level
        if confidence < 10:
            level = "VERY LOW"
            color = '#888'
        elif confidence < 20:
            level = "LOW"
            color = '#FFA500'
        elif confidence < 30:
            level = "MODERATE"
            color = '#FFD700'
        else:
            level = "HIGH"
            color = '#4CAF50'
        
        # Simple circular confidence meter - just the ring
        theta = np.linspace(0, 2*np.pi, 100)
        r_outer = 0.35
        r_inner = 0.28
        
        # Background ring
        x_outer = r_outer * np.cos(theta)
        y_outer = r_outer * np.sin(theta)
        x_inner = r_inner * np.cos(theta)
        y_inner = r_inner * np.sin(theta)
        ax.fill(np.concatenate([x_outer, x_inner[::-1]]), 
               np.concatenate([y_outer, y_inner[::-1]]),
               color=self.colors['grid'], alpha=0.3)
        
        # Filled portion based on confidence
        fill_theta = np.linspace(-np.pi/2, -np.pi/2 + 2*np.pi * (confidence/100), 100)
        fill_x_outer = r_outer * np.cos(fill_theta)
        fill_y_outer = r_outer * np.sin(fill_theta)
        fill_x_inner = r_inner * np.cos(fill_theta)
        fill_y_inner = r_inner * np.sin(fill_theta)
        ax.fill(np.concatenate([fill_x_outer, fill_x_inner[::-1]]), 
               np.concatenate([fill_y_outer, fill_y_inner[::-1]]),
               color=color, alpha=0.8)
        
        # Center text
        ax.text(0, 0.08, f"{confidence:.1f}%", 
               ha='center', va='center', fontsize=18, fontweight='bold',
               color=color)
        ax.text(0, -0.12, level, 
               ha='center', va='center', fontsize=9,
               color=self.colors['text'], alpha=0.8)
        
        ax.text(0, -0.45, 'Confidence', 
               ha='center', va='center', fontsize=10,
               color=self.colors['text'], alpha=0.7)
        
        ax.set_xlim(-0.5, 0.5)
        ax.set_ylim(-0.5, 0.5)
        ax.set_aspect('equal')
        ax.axis('off')
    
    def _plot_stats_comparison(self, ax, data):
        """Plot team statistics comparison with greater-than style"""
        stats_a = data['team_a_stats']
        stats_b = data['team_b_stats']
        
        team_a = data['team_a']
        team_b = data['team_b']
        
        # Metrics to compare
        metrics = [
            ('Win Rate', stats_a['win_rate'], stats_b['win_rate'], '%'),
            ('Map Win Rate', stats_a['map_win_rate'], stats_b['map_win_rate'], '%'),
            ('Avg K/D', stats_a['roster_quality']['avg_kd'], 
             stats_b['roster_quality']['avg_kd'], ''),
            ('Avg Rating', stats_a['roster_quality']['avg_rating'], 
             stats_b['roster_quality']['avg_rating'], '')
        ]
        
        # Set up the plot - tighter spacing
        ax.set_xlim(0, 10)
        ax.set_ylim(-0.5, len(metrics) - 0.5)
        
        for i, (metric, val_a, val_b, unit) in enumerate(metrics):
            y_pos = len(metrics) - 1 - i
            
            # Draw comparison
            # Team A value (left)
            format_str = '.1f' if unit == '%' else '.2f'
            ax.text(2, y_pos, f"{val_a:{format_str}}{unit}", 
                   ha='right', va='center', fontsize=11, fontweight='bold',
                   color=self.colors['team_a'] if val_a > val_b else self.colors['text'],
                   alpha=1.0 if val_a > val_b else 0.6)
            
            # Comparison symbol (center)
            if val_a > val_b:
                comparison = '>'
                ax.text(5, y_pos, comparison,
                       ha='center', va='center', fontsize=14, fontweight='bold',
                       color=self.colors['team_a'])
            elif val_b > val_a:
                comparison = '<'
                ax.text(5, y_pos, comparison,
                       ha='center', va='center', fontsize=14, fontweight='bold',
                       color=self.colors['team_b'])
            else:
                comparison = '='
                ax.text(5, y_pos, comparison,
                       ha='center', va='center', fontsize=14, fontweight='bold',
                       color=self.colors['text'], alpha=0.5)
            
            # Team B value (right)
            ax.text(8, y_pos, f"{val_b:{format_str}}{unit}", 
                   ha='left', va='center', fontsize=11, fontweight='bold',
                   color=self.colors['team_b'] if val_b > val_a else self.colors['text'],
                   alpha=1.0 if val_b > val_a else 0.6)
            
            # Metric label (below, smaller)
            ax.text(5, y_pos - 0.35, metric,
                   ha='center', va='top', fontsize=8,
                   color=self.colors['text'], alpha=0.7)
        
        # Add team names at top
        ax.text(2, len(metrics) - 0.3, team_a,
               ha='right', va='bottom', fontsize=9, fontweight='bold',
               color=self.colors['team_a'])
        ax.text(8, len(metrics) - 0.3, team_b,
               ha='left', va='bottom', fontsize=9, fontweight='bold',
               color=self.colors['team_b'])
        
        ax.set_title('STATS', fontsize=13, fontweight='bold',
                    pad=15, color=self.colors['accent'])
        ax.axis('off')
    
    def _plot_pickban_prediction(self, ax, data):
        """Plot predicted map pool from pick/ban simulation"""
        pick_ban = data.get('pick_ban_prediction', {})
        predicted_maps = pick_ban.get('predicted_maps', [])
        
        if not predicted_maps:
            ax.text(0.5, 0.5, 'No pick/ban data', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color=self.colors['text'], alpha=0.5)
            ax.axis('off')
            return
        
        # Take first 5 maps
        maps = predicted_maps[:5]
        
        ax.set_xlim(0, 10)
        ax.set_ylim(-0.5, len(maps) + 0.5)
        
        for i, map_pred in enumerate(maps):
            y_pos = len(maps) - i - 0.5
            
            map_num = map_pred['map_number']
            mode = map_pred['mode']
            map_name = map_pred['predicted_map']
            
            # Map number (left)
            ax.text(0.5, y_pos, f"Map {map_num}",
                   ha='left', va='center', fontsize=9, fontweight='bold',
                   color=self.colors['accent'])
            
            # Map and mode column (center)
            ax.text(3, y_pos + 0.1, map_name,
                   ha='left', va='center', fontsize=9, fontweight='bold',
                   color=self.colors['text'], alpha=0.9)
            ax.text(3, y_pos - 0.15, mode,
                   ha='left', va='center', fontsize=8,
                   color=self.colors['text'], alpha=0.7)
            
            # Win rates if available
            if 'team_a_winrate' in map_pred and 'team_b_winrate' in map_pred:
                wr_a = map_pred['team_a_winrate']
                wr_b = map_pred['team_b_winrate']
                
                # Determine which is higher
                if wr_a > wr_b:
                    color_a = self.colors['team_a']
                    color_b = self.colors['text']
                    alpha_a = 1.0
                    alpha_b = 0.5
                elif wr_b > wr_a:
                    color_a = self.colors['text']
                    color_b = self.colors['team_b']
                    alpha_a = 0.5
                    alpha_b = 1.0
                else:
                    color_a = color_b = self.colors['text']
                    alpha_a = alpha_b = 0.7
                
                # Display win rates with vs separator
                ax.text(6.5, y_pos, f"{wr_a:.0f}%",
                       ha='center', va='center', fontsize=10,
                       color=color_a, alpha=alpha_a, fontweight='bold')
                ax.text(7.5, y_pos, 'vs',
                       ha='center', va='center', fontsize=8,
                       color=self.colors['text'], alpha=0.5)
                ax.text(8.5, y_pos, f"{wr_b:.0f}%",
                       ha='center', va='center', fontsize=10,
                       color=color_b, alpha=alpha_b, fontweight='bold')
            
            # Separator line
            if i < len(maps) - 1:
                ax.plot([0.5, 9.5], [y_pos - 0.5, y_pos - 0.5],
                       color=self.colors['grid'], alpha=0.3, linewidth=0.5)
        
        ax.set_title('PREDICTED MAP POOL', fontsize=13, fontweight='bold',
                    pad=15, color=self.colors['accent'])
        ax.axis('off')
    
    def _plot_mode_breakdown(self, ax, data):
        """Plot mode-by-mode breakdown"""
        map_predictions = data.get('map_predictions', [])
        
        if not map_predictions:
            ax.text(0.5, 0.5, 'No map predictions available', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color=self.colors['text'], alpha=0.5)
            ax.axis('off')
            return
        
        # Take first 5 maps
        maps = map_predictions[:5]
        x = np.arange(len(maps))
        
        probs_a = [m['team_a_probability'] for m in maps]
        probs_b = [m['team_b_probability'] for m in maps]
        labels = [f"Map {i+1}\n{m['mode']}" for i, m in enumerate(maps)]
        
        width = 0.35
        bars1 = ax.bar(x - width/2, probs_a, width, label=data['team_a'],
                      color=self.colors['team_a'], alpha=0.8)
        bars2 = ax.bar(x + width/2, probs_b, width, label=data['team_b'],
                      color=self.colors['team_b'], alpha=0.8)
        
        # Add winner indicators
        for i, m in enumerate(maps):
            winner = m.get('predicted_winner')
            if winner:
                marker = '→' if winner == data['team_a'] else '←'
                y_pos = max(probs_a[i], probs_b[i]) + 5
                ax.text(i, y_pos, marker, ha='center', va='bottom',
                       fontsize=16, fontweight='bold', 
                       color=self.colors['accent'])
        
        ax.set_ylabel('Win Probability (%)', fontsize=10, color=self.colors['text'])
        ax.set_title('MAP-BY-MAP PREDICTIONS', fontsize=14, fontweight='bold',
                    pad=15, color=self.colors['accent'])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylim(0, 110)
        ax.legend(loc='upper right', fontsize=10, framealpha=0.8)
        ax.grid(axis='y', alpha=0.2, color=self.colors['grid'])
        ax.axhline(50, color=self.colors['text'], linestyle='--', 
                  alpha=0.3, linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.patch.set_alpha(0)  # Transparent background


def generate_prediction_graphic(prediction_data: dict, output_dir: str = 'outputs', 
                                filename: str = None) -> str:
    """
    Convenience function to generate prediction graphic
    
    Args:
        prediction_data: Prediction results dictionary
        output_dir: Output directory for graphics
        filename: Optional custom filename
    
    Returns:
        Path to generated graphic
    """
    generator = PredictionGraphics(output_dir=output_dir)
    return generator.generate_prediction_graphic(prediction_data, filename)
