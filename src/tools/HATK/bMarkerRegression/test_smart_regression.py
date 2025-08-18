#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_smart_regression.py

Unit tests for the SmartRegression module.
Tests core functionality and integration with YAML configuration.
"""

import unittest
import os
import tempfile
import pandas as pd
import numpy as np
import yaml
from pathlib import Path

# Add module to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from SmartRegression import SmartRegression


class TestSmartRegression(unittest.TestCase):
    """Test cases for SmartRegression functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.bfile_prefix = os.path.join(self.test_dir, "test_data")
        
        # Create mock PLINK files
        self._create_mock_plink_files()
        
        # Create mock YAML config
        self.config_file = os.path.join(self.test_dir, "test_config.yaml")
        self._create_mock_config()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
    
    def _create_mock_config(self):
        """Create mock YAML configuration file."""
        config = {
            "_bfile_prefix": self.bfile_prefix,
            "_out": os.path.join(self.test_dir, "test_output"),
            "_pheno_file": None,
            "_pheno_name": None,
            "_covar_file": None,
            "_covar_names": [],
            "_analysis_settings": {
                "automatic_phenotype_detection": True,
                "regression_type_selection": "automatic",
                "hla_optimized": True
            },
            "_logging": {
                "verbose": False
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
    
    def _create_mock_plink_files(self):
        """Create minimal mock PLINK files for testing."""
        # Create .fam file with binary phenotype
        fam_data = [
            ["FAM001", "IND001", "0", "0", "1", "1"],
            ["FAM002", "IND002", "0", "0", "2", "2"],
            ["FAM003", "IND003", "0", "0", "1", "1"],
            ["FAM004", "IND004", "0", "0", "2", "2"],
            ["FAM005", "IND005", "0", "0", "1", "1"]
        ]
        
        fam_df = pd.DataFrame(fam_data)
        fam_df.to_csv(self.bfile_prefix + ".fam", sep=' ', header=False, index=False)
        
        # Create .bim file
        bim_data = [
            ["6", "rs123", "0", "30000000", "A", "G"],
            ["6", "rs456", "0", "30000100", "C", "T"],
            ["6", "HLA_A_01", "0", "30000200", "A", "T"]
        ]
        bim_df = pd.DataFrame(bim_data)
        bim_df.to_csv(self.bfile_prefix + ".bim", sep='\t', header=False, index=False)
        
        # Create minimal .bed file (magic number only)
        with open(self.bfile_prefix + ".bed", 'wb') as f:
            # PLINK bed magic number
            f.write(bytes([0x6c, 0x1b, 0x01]))
    
    def test_phenotype_detection_binary(self):
        """Test binary phenotype detection."""
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            verbose=False
        )
        
        phenotype_type = smart_reg.analyze_phenotype()
        self.assertEqual(phenotype_type, "Binary")
        self.assertEqual(smart_reg.regression_type, "logistic")
    
    def test_phenotype_detection_continuous(self):
        """Test continuous phenotype detection."""
        # Create .fam file with continuous phenotype
        fam_data = []
        np.random.seed(42)
        for i in range(20):
            phenotype = np.random.normal(100, 15)  # Continuous values
            fam_data.append([f"FAM{i:03d}", f"IND{i:03d}", "0", "0", "1", f"{phenotype:.2f}"])
        
        fam_df = pd.DataFrame(fam_data)
        fam_df.to_csv(self.bfile_prefix + ".fam", sep=' ', header=False, index=False)
        
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            verbose=False
        )
        
        phenotype_type = smart_reg.analyze_phenotype()
        self.assertEqual(phenotype_type, "Continuous")
        self.assertEqual(smart_reg.regression_type, "linear")
    
    def test_external_phenotype_file(self):
        """Test using external phenotype file."""
        # Create external phenotype file
        pheno_file = os.path.join(self.test_dir, "phenotypes.txt")
        pheno_data = pd.DataFrame({
            'FID': ['FAM001', 'FAM002', 'FAM003'],
            'IID': ['IND001', 'IND002', 'IND003'],
            'Disease': [1, 2, 1],
            'Severity': [3.5, 4.2, 2.8]
        })
        pheno_data.to_csv(pheno_file, sep='\t', index=False)
        
        # Update config with external phenotype
        config = {
            "_bfile_prefix": self.bfile_prefix,
            "_out": os.path.join(self.test_dir, "test_output"),
            "_pheno_file": pheno_file,
            "_pheno_name": "Disease",
            "_logging": {"verbose": False}
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
        
        # Test binary phenotype
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            pheno_file=pheno_file,
            pheno_name="Disease",
            verbose=False
        )
        
        phenotype_type = smart_reg.analyze_phenotype()
        self.assertEqual(phenotype_type, "Binary")
        
        # Test continuous phenotype with updated config
        config["_pheno_name"] = "Severity"
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
        
        smart_reg2 = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output2"),
            pheno_file=pheno_file,
            pheno_name="Severity",
            verbose=False
        )
        
        phenotype_type2 = smart_reg2.analyze_phenotype()
        self.assertEqual(phenotype_type2, "Continuous")
    
    def test_file_verification(self):
        """Test input file verification."""
        # Test with missing file
        with self.assertRaises(FileNotFoundError):
            SmartRegression(
                bfile_prefix="non_existent_file",
                output_prefix="test",
                verbose=False
            )
    
    def test_covariate_handling(self):
        """Test covariate handling with configuration."""
        # Create covariate file
        covar_file = os.path.join(self.test_dir, "covariates.txt")
        covar_data = pd.DataFrame({
            'FID': ['FAM001', 'FAM002', 'FAM003'],
            'IID': ['IND001', 'IND002', 'IND003'],
            'PC1': [0.1, 0.2, 0.3],
            'PC2': [-0.1, 0.1, 0.2],
            'Age': [25, 30, 35]
        })
        covar_data.to_csv(covar_file, sep='\t', index=False)
        
        # Update config with covariates
        config = {
            "_bfile_prefix": self.bfile_prefix,
            "_out": os.path.join(self.test_dir, "test_output"),
            "_covar_file": covar_file,
            "_covar_names": ["PC1", "PC2", "Age"],
            "_logging": {"verbose": False}
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
        
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            covar_file=covar_file,
            covar_names=["PC1", "PC2", "Age"],
            verbose=False
        )
        
        self.assertEqual(smart_reg.covar_file, covar_file)
        self.assertEqual(smart_reg.covar_names, ["PC1", "PC2", "Age"])
    
    def test_phenotype_validation(self):
        """Test phenotype validation method."""
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            verbose=False
        )
        
        validation_stats = smart_reg.validate_phenotype_distribution()
        
        # Check validation stats
        self.assertIn('n_samples', validation_stats)
        self.assertIn('unique_values', validation_stats)
        self.assertIn('value_counts', validation_stats)
        self.assertGreater(validation_stats['n_samples'], 0)
    
    def test_result_processing(self):
        """Test result processing with mock data."""
        # Create mock association results
        mock_results = pd.DataFrame({
            'CHR': [6, 6, 6],
            'SNP': ['rs123', 'HLA_A_01', 'rs456'],
            'BP': [30000000, 30000200, 30000100],
            'A1': ['A', 'A', 'C'],
            'TEST': ['ADD', 'ADD', 'ADD'],
            'NMISS': [100, 100, 100],
            'OR': [1.2, 1.5, 0.8],
            'SE': [0.1, 0.15, 0.12],
            'L95': [1.0, 1.2, 0.6],
            'U95': [1.4, 1.8, 1.0],
            'STAT': [2.0, 3.0, -1.5],
            'P': [0.045, 0.003, 0.13]
        })
        
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            verbose=False
        )
        
        # Set up mock results
        smart_reg.regression_type = "logistic"
        smart_reg.assoc_result = os.path.join(self.test_dir, "test_output.assoc.logistic")
        mock_results.to_csv(smart_reg.assoc_result, sep='\t', index=False)
        
        # Test result processing
        parsed_results = smart_reg.parse_results()
        self.assertEqual(len(parsed_results), 3)
        self.assertIn('NEGLOG10P', parsed_results.columns)
        
        # Test filtering
        significant = smart_reg.filter_results_by_significance(p_threshold=0.05)
        self.assertEqual(len(significant), 2)
        
        # Test HLA results
        hla_results = smart_reg.get_hla_specific_results()
        self.assertEqual(len(hla_results), 1)
        self.assertEqual(hla_results.iloc[0]['SNP'], 'HLA_A_01')
    
    def test_export_functionality(self):
        """Test result export functionality."""
        mock_results = pd.DataFrame({
            'SNP': ['rs123', 'rs456'],
            'P': [0.01, 0.05],
            'OR': [1.2, 1.1]
        })
        
        smart_reg = SmartRegression(
            bfile_prefix=self.bfile_prefix,
            output_prefix=os.path.join(self.test_dir, "test_output"),
            verbose=False
        )
        
        smart_reg.summary_stats = mock_results
        
        # Test exports
        csv_file = smart_reg.export_results(format='csv')
        self.assertTrue(os.path.exists(csv_file))
        self.assertTrue(csv_file.endswith('.csv'))
        
        tsv_file = smart_reg.export_results(format='tsv', 
                                          filename=os.path.join(self.test_dir, "custom.tsv"))
        self.assertTrue(os.path.exists(tsv_file))
        self.assertTrue(tsv_file.endswith('.tsv'))


if __name__ == '__main__':
    unittest.main()