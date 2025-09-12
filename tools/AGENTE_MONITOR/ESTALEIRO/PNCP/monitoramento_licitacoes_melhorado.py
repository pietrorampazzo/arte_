"""
Enhanced tender monitoring system.
Builds upon existing monitoring capabilities with improved reliability.
"""
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Optional
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import config_endpoints as config
import utils_licitacoes as utils
from api_consolidada import UnifiedAPIClient

logger = logging.getLogger(__name__)

class TenderMonitor:
    def __init__(self):
        self.api_client = UnifiedAPIClient()
        self.previous_results = {}
        self.current_results = {}

    def load_previous_results(self) -> None:
        """
        Load previous monitoring results if available
        """
        result_file = os.path.join(
            config.EXCEL_CONFIG["output_dir"],
            "arte_heavy_Arte.xlsx"
        )
        if os.path.exists(result_file):
            try:
                df = pd.read_excel(result_file)
                self.previous_results = df.set_index(["UASG", "EDITAL", "Item"]).to_dict("index")
            except Exception as e:
                logger.error(f"Error loading previous results: {str(e)}")

    def detect_status_changes(self) -> List[Dict]:
        """
        Detect changes in tender status
        """
        changes = []
        for key, current in self.current_results.items():
            previous = self.previous_results.get(key, {})
            if previous.get("Status") != current.get("Status"):
                changes.append({
                    "tender": key,
                    "old_status": previous.get("Status", "N/A"),
                    "new_status": current.get("Status"),
                    "timestamp": datetime.now().isoformat()
                })
        return changes

    def process_tender(self, row: pd.Series) -> Dict:
        """
        Process single tender and get its status
        """
        try:
            response = self.api_client.get_tender_status(
                str(row["UASG"]),
                str(row["EDITAL"])
            )
            normalized = self.api_client.normalize_response(response)
            
            return {
                "UASG": row["UASG"],
                "EDITAL": row["EDITAL"],
                "Item": row["Item"],
                "Status": normalized["status"],
                "Rank": normalized["rank"],
                "Adjudicada": normalized["adjudicada"],
                "Fonte": normalized["source"],
                "Última Atualização": normalized["timestamp"]
            }
        except Exception as e:
            logger.error(f"Error processing tender {row['UASG']}_{row['EDITAL']}: {str(e)}")
            return {
                "UASG": row["UASG"],
                "EDITAL": row["EDITAL"],
                "Item": row["Item"],
                "Status": "Erro",
                "Última Atualização": datetime.now().isoformat()
            }

    def monitor_tenders(self, max_workers: int = 5) -> None:
        """
        Monitor all tenders in parallel
        """
        self.load_previous_results()
        
        try:
            df = utils.load_excel_data()
            results = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_row = {
                    executor.submit(self.process_tender, row): row
                    for _, row in df.iterrows()
                }
                
                for future in as_completed(future_to_row):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing tender: {str(e)}")
            
            # Convert results to DataFrame
            results_df = pd.DataFrame(results)
            
            # Update current results
            self.current_results = results_df.set_index(
                ["UASG", "EDITAL", "Item"]
            ).to_dict("index")
            
            # Detect and log changes
            changes = self.detect_status_changes()
            if changes:
                logger.info("Status changes detected:")
                for change in changes:
                    logger.info(
                        f"Tender {change['tender']}: "
                        f"{change['old_status']} -> {change['new_status']}"
                    )
            
            # Save results
            output_file = os.path.join(
                config.EXCEL_CONFIG["output_dir"],
                "arte_heavy_Arte.xlsx"
            )
            results_df.to_excel(output_file, index=False)
            logger.info(f"Results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error monitoring tenders: {str(e)}")
            raise

def main():
    """
    Main function to run tender monitoring
    """
    try:
        monitor = TenderMonitor()
        monitor.monitor_tenders()
        logger.info("Tender monitoring completed successfully")
    except Exception as e:
        logger.error(f"Error in tender monitoring: {str(e)}")
        raise

if __name__ == "__main__":
    main()
