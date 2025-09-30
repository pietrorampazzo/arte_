"""
Comprehensive testing script for tender monitoring endpoints.
Tests all available endpoints against actual tender data.
"""
import os
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import config_endpoints as config
import utils_licitacoes as utils
from endpoints_estruturados import EndpointTester

logger = logging.getLogger(__name__)

class EndpointTestRunner:
    def __init__(self):
        self.tester = EndpointTester()
        self.results = {}
        self.performance_metrics = {}

    def load_tender_data(self) -> pd.DataFrame:
        """
        Load tender data from TRELLO.xlsx
        """
        logger.info("Loading tender data from Excel...")
        return utils.load_excel_data()

    def test_single_tender(self, uasg: str, edital: str) -> Dict:
        """
        Test all endpoints for a single tender
        """
        start_time = datetime.now()
        
        try:
            results = self.tester.test_all_endpoints(uasg, edital)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "uasg": uasg,
                "edital": edital,
                "results": results,
                "duration": duration,
                "timestamp": end_time.isoformat(),
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error testing tender UASG={uasg}, EDITAL={edital}: {str(e)}")
            return {
                "uasg": uasg,
                "edital": edital,
                "error": str(e),
                "status": "error"
            }

    def run_tests(self, max_workers: int = 5) -> None:
        """
        Run tests for all tenders in parallel
        """
        df = self.load_tender_data()
        logger.info(f"Starting tests for {len(df)} tenders...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_tender = {
                executor.submit(
                    self.test_single_tender,
                    str(row["UASG"]),
                    str(row["EDITAL"])
                ): (str(row["UASG"]), str(row["EDITAL"]))
                for _, row in df.iterrows()
            }

            for future in as_completed(future_to_tender):
                uasg, edital = future_to_tender[future]
                try:
                    result = future.result()
                    self.results[f"{uasg}_{edital}"] = result
                except Exception as e:
                    logger.error(f"Error processing tender {uasg}_{edital}: {str(e)}")

    def analyze_results(self) -> Dict:
        """
        Analyze test results and generate metrics
        """
        metrics = {
            "total_tenders": len(self.results),
            "successful_tests": sum(1 for r in self.results.values() if r["status"] == "success"),
            "failed_tests": sum(1 for r in self.results.values() if r["status"] == "error"),
            "api_success_rates": {
                "pncp": 0,
                "comprasgov": 0,
                "transparencia": 0
            },
            "average_duration": 0,
            "working_endpoints": {}
        }

        durations = []
        working_endpoints = {
            "pncp": set(),
            "comprasgov": set(),
            "transparencia": set()
        }

        for result in self.results.values():
            if result["status"] == "success":
                durations.append(result["duration"])
                
                for api_name, api_results in result["results"].items():
                    working = [name for name, data in api_results.items() 
                             if data["status"] == "working"]
                    working_endpoints[api_name].update(working)

        if durations:
            metrics["average_duration"] = sum(durations) / len(durations)

        for api_name, endpoints in working_endpoints.items():
            metrics["working_endpoints"][api_name] = list(endpoints)
            if metrics["total_tenders"] > 0:
                metrics["api_success_rates"][api_name] = (
                    len(endpoints) / (metrics["total_tenders"] * len(config.ENDPOINTS[api_name]))
                ) * 100

        return metrics

    def save_results(self) -> None:
        """
        Save test results and metrics
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_file = os.path.join(
            config.EXCEL_CONFIG["output_dir"],
            f"endpoint_test_results_{timestamp}.json"
        )
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Save metrics
        metrics = self.analyze_results()
        metrics_file = os.path.join(
            config.EXCEL_CONFIG["output_dir"],
            f"endpoint_test_metrics_{timestamp}.json"
        )
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        logger.info(f"Metrics saved to {metrics_file}")

def main():
    """
    Main function to run endpoint tests
    """
    try:
        runner = EndpointTestRunner()
        runner.run_tests()
        runner.save_results()
        logger.info("Endpoint testing completed successfully")
    except Exception as e:
        logger.error(f"Error running endpoint tests: {str(e)}")
        raise

if __name__ == "__main__":
    main()
