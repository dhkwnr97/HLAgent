import logging
from typing import Dict, Any
import pandas as pd

from pathlib import Path
import sys

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ImputationQualityChecker:
    """Checks the quality of HLA imputation results."""

    def __init__(self):
        logger.info("ImputationQualityChecker initialized.")

    def check_imputation_quality(self, alleles_file: str) -> Dict[str, Any]:
        """
        Check imputation quality metrics from a CookHLA alleles file.
        
        Args:
            alleles_file: Path to CookHLA alleles file.
            
        Returns:
            A dictionary containing quality metrics.
        """
        try:
            # Check if file exists using pandas' helper
            if not pd.io.common.file_exists(alleles_file):
                logger.error(f"Alleles file not found: {alleles_file}")
                return {"error": "Alleles file not found."}

            # Read alleles file, handling multiple spaces as separators
            df = pd.read_csv(alleles_file, sep='\s+')
            
            if df.empty:
                logger.warning(f"Alleles file is empty: {alleles_file}")
                return {"error": "Alleles file is empty."}

            metrics = {
                'n_individuals': df['IID'].nunique(),
                'n_alleles': len(df),
                'genes': {}
            }
            
            # Per-gene metrics
            if 'Gene' not in df.columns or 'Score' not in df.columns or '4digit' not in df.columns:
                logger.error("Alleles file is missing required columns (Gene, Score, 4digit).")
                return {"error": "Missing required columns in alleles file."}
                
            for gene in df['Gene'].unique():
                gene_df = df[df['Gene'] == gene]
                
                # Average confidence score
                avg_score = gene_df['Score'].mean()
                
                # Allele frequency
                allele_counts = gene_df['4digit'].value_counts()
                
                metrics['genes'][gene] = {
                    'n_alleles': len(gene_df),
                    'avg_confidence': float(avg_score),
                    'n_unique_alleles': int(allele_counts.nunique()),
                    'most_common': allele_counts.head(5).to_dict()
                }
            
            metrics['avg_confidence'] = float(df['Score'].mean())
            metrics['low_confidence_rate'] = float((df['Score'] < 0.5).mean())
            
            logger.info(f"Successfully calculated quality metrics for {alleles_file}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error checking imputation quality for {alleles_file}: {e}")
            return {"error": str(e)}