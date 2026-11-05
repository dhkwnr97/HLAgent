#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
metaanalPlot.py
==============
Visualization script for meta-analysis results.

This script generates various plots to visualize and interpret the results
from a meta-analysis, including Q-Q, Forest, Funnel plots, and meta-analysis
specific visualizations.

Usage:
    python metaanalPlot.py --meta-file <path_to.meta> --output-prefix <prefix> [options]

Author: HLAgent Development Team
Date: 2025
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os
import warnings

def plot_manhattan(meta_df, s1_logistic_file, output_file, title='Manhattan Plot - Meta-Analysis Results'):
    """
    Generate Manhattan plot for meta-analysis results.
    
    Args:
        meta_df: Meta-analysis results DataFrame
        s1_logistic_file: Path to study 1 logistic regression file (for CHR and BP info)
        output_file: Output file path
        title: Plot title
    """
    try:
        # Import read_logistic_result function
        import sys
        from pathlib import Path
        
        # Add the project root to Python path if not already there
        project_root = str(Path(__file__).parents[4])
        if project_root not in sys.path:
            sys.path.append(project_root)
        
        from hatk_port.MetaAnalysis.metaanal_utils import read_logistic_result
        
        # Read study 1 logistic results to get CHR and BP information
        s1_df = pd.read_csv(s1_logistic_file, sep=r'\s+', header=0, engine='python')
        
        # Check if required columns exist
        if not all(col in s1_df.columns for col in ['SNP', 'CHR', 'BP']):
            print(f"Warning: Missing CHR or BP columns in {s1_logistic_file}. Skipping Manhattan plot.")
            return
        
        # Merge meta-analysis results with position information
        manhattan_df = meta_df.merge(s1_df[['SNP', 'CHR', 'BP']], on='SNP', how='inner')
        
        if manhattan_df.empty:
            print("Warning: No matching SNPs found for Manhattan plot. Skipping.")
            return
        
        # Calculate -log10(p-values)
        manhattan_df['-log10P'] = -np.log10(manhattan_df['MetaP'])
        
        # Sort by chromosome and position
        manhattan_df = manhattan_df.sort_values(['CHR', 'BP'])
        
        # Create cumulative position for x-axis
        manhattan_df['cumulative_pos'] = 0
        cumulative_pos = 0
        chr_centers = {}
        
        for chr_num in sorted(manhattan_df['CHR'].unique()):
            chr_data = manhattan_df[manhattan_df['CHR'] == chr_num]
            manhattan_df.loc[manhattan_df['CHR'] == chr_num, 'cumulative_pos'] = cumulative_pos + chr_data['BP']
            chr_centers[chr_num] = cumulative_pos + chr_data['BP'].median()
            cumulative_pos += chr_data['BP'].max() + 1e6  # Add gap between chromosomes
        
        # Create Manhattan plot
        plt.figure(figsize=(16, 8))
        
        # Define colors for alternating chromosomes
        colors = ['#1f77b4', '#ff7f0e']
        
        # Plot points for each chromosome
        for i, chr_num in enumerate(sorted(manhattan_df['CHR'].unique())):
            chr_data = manhattan_df[manhattan_df['CHR'] == chr_num]
            color = colors[i % 2]
            plt.scatter(chr_data['cumulative_pos'], chr_data['-log10P'], 
                       c=color, s=8, alpha=0.7, label=f'Chr {chr_num}' if i < 2 else "")
        
        # Add significance lines
        plt.axhline(y=-np.log10(5e-8), color='red', linestyle='--', linewidth=1.5, 
                   label='Genome-wide significance (5×10⁻⁸)')
        plt.axhline(y=-np.log10(1e-5), color='orange', linestyle='--', linewidth=1, 
                   label='Suggestive significance (1×10⁻⁵)')
        
        # Customize plot
        plt.xlabel('Chromosome', fontsize=12)
        plt.ylabel('-log₁₀(P-value)', fontsize=12)
        plt.title(title, fontsize=14, fontweight='bold')
        
        # Set x-axis ticks to chromosome centers
        plt.xticks(list(chr_centers.values()), list(chr_centers.keys()))
        
        # Add legend
        plt.legend(loc='upper right', fontsize=10)
        
        # Set y-axis limits
        plt.ylim(0, max(manhattan_df['-log10P']) * 1.1)
        
        # Add grid
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Print summary
        significant_snps = len(manhattan_df[manhattan_df['MetaP'] < 5e-8])
        suggestive_snps = len(manhattan_df[manhattan_df['MetaP'] < 1e-5])
        
        print(f"Manhattan plot saved to {output_file}")
        print(f"  - Total SNPs plotted: {len(manhattan_df)}")
        print(f"  - Genome-wide significant SNPs (P < 5×10⁻⁸): {significant_snps}")
        print(f"  - Suggestive significant SNPs (P < 1×10⁻⁵): {suggestive_snps}")
        
    except Exception as e:
        print(f"Warning: Error creating Manhattan plot: {e}")
        print("Skipping Manhattan plot.")

def plot_qq(df, output_file, title='Q-Q Plot'):
    """
    Generates a Q-Q plot of p-values.
    """
    p_values = df['MetaP'].dropna()
    observed = -np.log10(np.sort(p_values))
    expected = -np.log10(np.arange(1, len(observed) + 1) / (len(observed) + 1))

    plt.figure(figsize=(8, 8))
    plt.scatter(expected, observed, s=8, alpha=0.6)
    plt.plot([0, max(expected)], [0, max(expected)], color='red', linestyle='--', linewidth=2)
    plt.xlabel('Expected -log10(P-value)', fontsize=12)
    plt.ylabel('Observed -log10(P-value)', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    
    # Add lambda inflation factor
    lambda_gc = np.median(observed) / np.median(expected)
    plt.text(0.05, 0.95, f'λ = {lambda_gc:.3f}', transform=plt.gca().transAxes, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Q-Q plot saved to {output_file}")

def plot_effect_size_distribution(df, output_file, title='Effect Size Distribution'):
    """
    Plot distribution of effect sizes (BETA) from meta-analysis.
    """
    plt.figure(figsize=(12, 8))
    
    # Main histogram
    plt.subplot(2, 2, 1)
    plt.hist(df['BETA'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
    plt.xlabel('Effect Size (BETA)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Effect Size Distribution', fontsize=14, fontweight='bold')
    plt.axvline(df['BETA'].mean(), color='red', linestyle='--', label=f'Mean: {df["BETA"].mean():.4f}')
    plt.axvline(0, color='black', linestyle='-', alpha=0.5, label='Null effect')
    plt.legend()
    
    # Box plot
    plt.subplot(2, 2, 2)
    plt.boxplot(df['BETA'], vert=True)
    plt.ylabel('Effect Size (BETA)', fontsize=12)
    plt.title('Effect Size Box Plot', fontsize=14, fontweight='bold')
    
    # Standard Error vs Effect Size
    plt.subplot(2, 2, 3)
    plt.scatter(df['BETA'], df['SE'], s=8, alpha=0.6, color='green')
    plt.xlabel('Effect Size (BETA)', fontsize=12)
    plt.ylabel('Standard Error (SE)', fontsize=12)
    plt.title('Effect Size vs Standard Error', fontsize=14, fontweight='bold')
    
    # P-value distribution
    plt.subplot(2, 2, 4)
    plt.hist(-np.log10(df['MetaP']), bins=50, alpha=0.7, color='orange', edgecolor='black')
    plt.xlabel('-log10(P-value)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('P-value Distribution', fontsize=14, fontweight='bold')
    plt.axvline(-np.log10(5e-8), color='red', linestyle='--', label='Genome-wide significance')
    plt.axvline(-np.log10(1e-5), color='orange', linestyle='--', label='Suggestive significance')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Effect size distribution plot saved to {output_file}")

def plot_study_comparison(meta_df, s1_df, s2_df, output_file, title='Study Comparison'):
    """
    Compare effect sizes between the two studies.
    """
    # Prefer 'OR' if present, else 'BETA'
    s1_col = 'OR' if 'OR' in s1_df.columns else 'BETA'
    s2_col = 'OR' if 'OR' in s2_df.columns else 'BETA'
    meta_col = 'OR' if 'OR' in meta_df.columns else 'BETA'

    # Merge data with proper suffixes - include SE columns
    s1_df_renamed = s1_df[['SNP', s1_col, 'SE']].copy()
    s1_df_renamed = s1_df_renamed.rename(columns={s1_col: f'{s1_col}_s1', 'SE': 'SE_s1'})
        
    s2_df_renamed = s2_df[['SNP', s2_col, 'SE']].copy()
    s2_df_renamed = s2_df_renamed.rename(columns={s2_col: f'{s2_col}_s2', 'SE': 'SE_s2'})
        
    comparison_df = meta_df.merge(s1_df_renamed, on='SNP', suffixes=('_meta', ''))
    comparison_df = comparison_df.merge(s2_df_renamed, on='SNP', suffixes=('', ''))

    if meta_col in comparison_df.columns and f'{meta_col}_meta' not in comparison_df.columns:
        comparison_df = comparison_df.rename(columns={meta_col: f'{meta_col}_meta'})
        comparison_df = comparison_df.rename(columns={'SE': f'SE_meta'})
    
    if comparison_df.empty:
        print("Warning: No common SNPs found for study comparison plot. Skipping.")
        return

    plt.figure(figsize=(15, 10))
    
    # Study 1 vs Study 2
    plt.subplot(2, 3, 1)
    plt.scatter(comparison_df[f'{s1_col}_s1'], comparison_df[f'{s2_col}_s2'], s=8, alpha=0.6)
    plt.xlabel(f'Study 1 {s1_col}', fontsize=12)
    plt.ylabel(f'Study 2 {s2_col}', fontsize=12)
    plt.title('Study 1 vs Study 2', fontsize=14, fontweight='bold')
    # Add y=x line
    min_val = min(comparison_df[f'{s1_col}_s1'].min(), comparison_df[f'{s2_col}_s2'].min())
    max_val = max(comparison_df[f'{s1_col}_s1'].max(), comparison_df[f'{s2_col}_s2'].max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.7, label='y=x')
    plt.legend()    
    # Add correlation line and text
    correlation = comparison_df[f'{s1_col}_s1'].corr(comparison_df[f'{s2_col}_s2'])
    # Calculate regression line
    z = np.polyfit(comparison_df[f'{s1_col}_s1'], comparison_df[f'{s2_col}_s2'], 1)
    p = np.poly1d(z)
    # Plot regression line
    x_range = np.linspace(comparison_df[f'{s1_col}_s1'].min(), comparison_df[f'{s1_col}_s1'].max(), 100)
    plt.plot(x_range, p(x_range), "b-", alpha=0.8, linewidth=2, label=f'Correlation line (r={correlation:.3f})')
    # Add correlation text
    plt.text(0.05, 0.95, f'r = {correlation:.3f}', transform=plt.gca().transAxes,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
    
    # Study 1 vs Meta
    plt.subplot(2, 3, 2)
    plt.scatter(comparison_df[f'{s1_col}_s1'], comparison_df[f'{meta_col}_meta'], s=8, alpha=0.6, color='red')
    plt.xlabel(f'Study 1 {s1_col}', fontsize=12)
    plt.ylabel(f'Meta-analysis {meta_col}', fontsize=12)
    plt.title('Study 1 vs Meta-analysis', fontsize=14, fontweight='bold')
    
    # Add y=x line
    min_val = min(comparison_df[f'{s1_col}_s1'].min(), comparison_df[f'{meta_col}_meta'].min())
    max_val = max(comparison_df[f'{s1_col}_s1'].max(), comparison_df[f'{meta_col}_meta'].max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.7, label='y=x')
    plt.legend()
    
    # Study 2 vs Meta
    plt.subplot(2, 3, 3)
    plt.scatter(comparison_df[f'{s2_col}_s2'], comparison_df[f'{meta_col}_meta'], s=8, alpha=0.6, color='green')
    plt.xlabel(f'Study 2 {s2_col}', fontsize=12)
    plt.ylabel(f'Meta-analysis {meta_col}', fontsize=12)
    plt.title('Study 2 vs Meta-analysis', fontsize=14, fontweight='bold')
    
    # Add y=x line
    min_val = min(comparison_df[f'{s2_col}_s2'].min(), comparison_df[f'{meta_col}_meta'].min())
    max_val = max(comparison_df[f'{s2_col}_s2'].max(), comparison_df[f'{meta_col}_meta'].max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.7, label='y=x')
    plt.legend()
    
    # Effect size differences
    plt.subplot(2, 3, 4)
    effect_diff = comparison_df[f'{s1_col}_s1'] - comparison_df[f'{s2_col}_s2']
    plt.hist(effect_diff, bins=50, alpha=0.7, color='purple', edgecolor='black')
    plt.xlabel(f'{s1_col} Difference (Study 1 - Study 2)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'{s1_col} Differences', fontsize=14, fontweight='bold')
    plt.axvline(0, color='red', linestyle='--', label='No difference')
    plt.legend()
    
    # Bland-Altman plot
    plt.subplot(2, 3, 5)
    mean_effects = (comparison_df[f'{s1_col}_s1'] + comparison_df[f'{s2_col}_s2']) / 2
    differences = comparison_df[f'{s1_col}_s1'] - comparison_df[f'{s2_col}_s2']
    plt.scatter(mean_effects, differences, s=8, alpha=0.6, color='orange')
    plt.xlabel(f'Mean {s1_col}', fontsize=12)
    plt.ylabel(f'Difference (Study 1 - Study 2)', fontsize=12)
    plt.title('Bland-Altman Plot', fontsize=14, fontweight='bold')
    plt.axhline(0, color='red', linestyle='--', alpha=0.5)
    
    # Heterogeneity analysis (only if SE columns exist)
    if 'SE_meta' in comparison_df.columns and 'SE_s1' in comparison_df.columns and 'SE_s2' in comparison_df.columns:
        plt.subplot(2, 3, 6)
        valid_se_s1 = comparison_df['SE_s1'].replace(0, np.nan)
        valid_se_s2 = comparison_df['SE_s2'].replace(0, np.nan)
        se_combined_sq = (valid_se_s1**2 + valid_se_s2**2) / 2
        se_combined_sq = se_combined_sq.replace([np.inf, -np.inf], np.nan).dropna()
        if not se_combined_sq.empty:
            se_ratio = comparison_df['SE_meta'] / np.sqrt(se_combined_sq)
            plt.hist(se_ratio.dropna(), bins=50, alpha=0.7, color='brown', edgecolor='black')
            plt.xlabel('SE Ratio (Meta / Average)', fontsize=12)
            plt.ylabel('Frequency', fontsize=12)
            plt.title('Heterogeneity Indicator', fontsize=14, fontweight='bold')
            plt.axvline(1, color='red', linestyle='--', alpha=0.5, label='No heterogeneity')
        else:
            print("Warning: Cannot calculate heterogeneity indicator due to invalid SE values.")
    else:
        print("Warning: SE columns missing, skipping heterogeneity indicator plot.")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Study comparison plot saved to {output_file}")

def plot_forest(meta_df, s1_df, s2_df, output_file, top_n=10, title='Forest Plot of Top Hits'):
    """
    Generates a forest plot for the top N hits from the meta-analysis.
    """
    top_snps = meta_df.nsmallest(top_n, 'MetaP')
    
    plot_data = []
    for _, row in top_snps.iterrows():
        snp = row['SNP']
        s1_data = s1_df[s1_df['SNP'] == snp]
        s2_data = s2_df[s2_df['SNP'] == snp]
        
        if not s1_data.empty:
            plot_data.append({'SNP': snp, 'Study': 'Study 1', 'BETA': s1_data.iloc[0]['BETA'], 'SE': s1_data.iloc[0]['SE']})
        if not s2_data.empty:
            plot_data.append({'SNP': snp, 'Study': 'Study 2', 'BETA': s2_data.iloc[0]['BETA'], 'SE': s2_data.iloc[0]['SE']})
        
        plot_data.append({'SNP': snp, 'Study': 'Meta-analysis', 'BETA': row['BETA'], 'SE': row['SE']})

    plot_df = pd.DataFrame(plot_data)

    fig, ax = plt.subplots(figsize=(12, top_n * 0.6))
    
    y_ticks = []
    y_pos = 0
    for snp in top_snps['SNP']:
        snp_data = plot_df[plot_df['SNP'] == snp]
        for _, study_row in snp_data.iterrows():
            beta, se = study_row['BETA'], study_row['SE']
            ci_lower, ci_upper = beta - 1.96 * se, beta + 1.96 * se
            
            color = 'black'
            marker = 'o'
            if study_row['Study'] == 'Meta-analysis':
                color = 'red'
                marker = 'D' # Diamond for meta-analysis

            ax.errorbar(x=[beta], y=[y_pos], xerr=[[beta - ci_lower], [ci_upper - beta]], 
                       fmt=marker, color=color, capsize=3, markersize=6)
            ax.text(ax.get_xlim()[1] + 0.05, y_pos, f"{study_row['Study']}", va='center', fontsize=10)
            y_pos -= 1

        y_ticks.append(y_pos + (len(snp_data)/2.0))
        ax.axhline(y=y_pos + 0.5, color='grey', linestyle=':', linewidth=0.5)
        y_pos -= 1

    ax.axvline(x=0, color='grey', linestyle='--')
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(top_snps['SNP'], fontsize=10)
    ax.set_xlabel('Effect Size (BETA)', fontsize=12)
    ax.set_ylabel('SNP', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Forest plot saved to {output_file}")

def plot_funnel(meta_df, output_file, title='Funnel Plot'):
    """
    Generates a funnel plot to check for publication bias.
    """
    beta = meta_df['BETA']
    se = meta_df['SE']
    
    plt.figure(figsize=(10, 8))
    
    # Main scatter plot
    plt.scatter(beta, se, s=12, alpha=0.6, color='blue', label='Individual studies')
    
    # Calculate weighted mean effect size
    weights = 1 / (se ** 2)
    weighted_mean = np.sum(beta * weights) / np.sum(weights)
    
    # Add summary effect line
    plt.axvline(x=weighted_mean, color='red', linestyle='--', linewidth=2, 
                label=f'Weighted mean: {weighted_mean:.4f}')
    
    # Add 95% confidence interval lines
    se_range = np.linspace(se.min(), se.max(), 100)
    plt.plot(weighted_mean - 1.96 * se_range, se_range, 'k--', alpha=0.7, 
             label='95% CI', linewidth=1.5)
    plt.plot(weighted_mean + 1.96 * se_range, se_range, 'k--', alpha=0.7, linewidth=1.5)
    
    # Add 99% confidence interval lines
    plt.plot(weighted_mean - 2.58 * se_range, se_range, 'k:', alpha=0.5, 
             label='99% CI', linewidth=1)
    plt.plot(weighted_mean + 2.58 * se_range, se_range, 'k:', alpha=0.5, linewidth=1)

    plt.gca().invert_yaxis()
    plt.xlabel('Effect Size (BETA)', fontsize=12)
    plt.ylabel('Standard Error', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    
    # Add interpretation text
    plt.figtext(0.02, 0.02, 
                'Interpretation:\n• Symmetric funnel = No publication bias\n• Asymmetric funnel = Possible publication bias\n• Points outside funnel = Potential outliers', 
                fontsize=9, style='italic', bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print statistical summary
    print(f"\n=== Funnel Plot Analysis ===")
    print(f"Total studies: {len(meta_df)}")
    print(f"Weighted mean effect: {weighted_mean:.4f}")
    print(f"Effect size range: {beta.min():.4f} to {beta.max():.4f}")
    print(f"Standard error range: {se.min():.4f} to {se.max():.4f}")
    
    # Check for asymmetry (simple test)
    positive_effects = beta > weighted_mean
    negative_effects = beta < weighted_mean
    print(f"Studies with positive effects: {positive_effects.sum()}")
    print(f"Studies with negative effects: {negative_effects.sum()}")
    
    if abs(positive_effects.sum() - negative_effects.sum()) > len(meta_df) * 0.2:
        print("⚠️  Warning: Possible asymmetry detected - check for publication bias")
    else:
        print("✓ Effect sizes appear reasonably symmetric")


def main():
    parser = argparse.ArgumentParser(description="Visualize meta-analysis results.")
    parser.add_argument('--meta-file', required=True, help='Path to the .meta result file.')
    parser.add_argument('--output-prefix', required=True, help='Prefix for output plot files.')
    parser.add_argument('--plot-types', nargs='+', default=['qq', 'manhattan', 'effect_dist', 'study_comp', 'forest', 'funnel'],
                        choices=['qq', 'manhattan', 'effect_dist', 'study_comp', 'forest', 'funnel'], 
                        help='Types of plots to generate.')
    
    # Study result files for comparison plots
    parser.add_argument('--s1-logistic-result', help='Path to study 1 logistic results for comparison plots.')
    parser.add_argument('--s2-logistic-result', help='Path to study 2 logistic results for comparison plots.')
    parser.add_argument('--top-n-forest', type=int, default=10, help='Number of top SNPs for the forest plot.')

    args = parser.parse_args()

    # Read meta-analysis results
    try:
        meta_df = pd.read_csv(args.meta_file, sep=r'\s+')
        print(f"✓ Loaded meta-analysis results: {len(meta_df)} variants")
    except FileNotFoundError:
        print(f"Error: Meta-analysis file not found at {args.meta_file}")
        return

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Generate plots
    if 'qq' in args.plot_types:
        plot_qq(meta_df, f"{args.output_prefix}_qq.png")

    if 'effect_dist' in args.plot_types:
        plot_effect_size_distribution(meta_df, f"{args.output_prefix}_effect_distribution.png")

    if 'study_comp' in args.plot_types:
        if args.s1_logistic_result and args.s2_logistic_result:
            try:
                # Try to import read_logistic_result from the correct path
                import sys
                from pathlib import Path
                
                # Add the project root to Python path if not already there
                project_root = str(Path(__file__).parents[4])
                if project_root not in sys.path:
                    sys.path.append(project_root)
                
                from hatk_port.MetaAnalysis.metaanal_utils import read_logistic_result
                s1_df = read_logistic_result(args.s1_logistic_result)
                s2_df = read_logistic_result(args.s2_logistic_result)
                plot_study_comparison(meta_df, s1_df, s2_df, f"{args.output_prefix}_study_comparison.png")
            except FileNotFoundError as e:
                print(f"Warning: Could not find study result files: {e}")
                print("Skipping study comparison plot.")
            except ImportError as e:
                print(f"Warning: Could not import read_logistic_result: {e}")
                print("Skipping study comparison plot.")
            except Exception as e:
                print(f"Warning: Error processing logistic results: {e}")
                print("Skipping study comparison plot.")
        else:
            print("Warning: --s1-logistic-result and --s2-logistic-result are required for the study comparison plot. Skipping.")

    if 'forest' in args.plot_types:
        if args.s1_logistic_result and args.s2_logistic_result:
            try:
                # Try to import read_logistic_result from the correct path
                import sys
                from pathlib import Path
                
                # Add the project root to Python path if not already there
                project_root = str(Path(__file__).parents[4])
                if project_root not in sys.path:
                    sys.path.append(project_root)
                
                from hatk_port.MetaAnalysis.metaanal_utils import read_logistic_result
                s1_df = read_logistic_result(args.s1_logistic_result)
                s2_df = read_logistic_result(args.s2_logistic_result)
                plot_forest(meta_df, s1_df, s2_df, f"{args.output_prefix}_forest.png", args.top_n_forest)
            except FileNotFoundError as e:
                print(f"Warning: Could not find study result files: {e}")
                print("Skipping forest plot.")
            except ImportError as e:
                print(f"Warning: Could not import read_logistic_result: {e}")
                print("Skipping forest plot.")
            except Exception as e:
                print(f"Warning: Error processing logistic results: {e}")
                print("Skipping forest plot.")
        else:
            print("Warning: --s1-logistic-result and --s2-logistic-result are required for the forest plot. Skipping.")

    if 'funnel' in args.plot_types:
        plot_funnel(meta_df, f"{args.output_prefix}_funnel.png")

    if 'manhattan' in args.plot_types:
        if args.s1_logistic_result:
            plot_manhattan(meta_df, args.s1_logistic_result, f"{args.output_prefix}_manhattan.png")
        else:
            print("Warning: --s1-logistic-result is required for Manhattan plot. Skipping.")

if __name__ == '__main__':
    main() 