"""
Comprehensive reporting script for endpoint functionality.
Generates detailed documentation of working endpoints.
"""
import json
import os
from datetime import datetime
import logging
from typing import Dict, List
import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate

import config_endpoints as config
from teste_endpoints_licitacoes import EndpointTestRunner

logger = logging.getLogger(__name__)

class EndpointReportGenerator:
    def __init__(self):
        self.test_runner = EndpointTestRunner()
        self.results = {}
        self.metrics = {}

    def run_tests(self) -> None:
        """
        Run comprehensive endpoint tests
        """
        logger.info("Starting endpoint tests...")
        self.test_runner.run_tests()
        self.results = self.test_runner.results
        self.metrics = self.test_runner.analyze_results()

    def generate_summary_table(self) -> str:
        """
        Generate summary table of endpoint performance
        """
        summary_data = []
        
        for api_name in ["pncp", "comprasgov", "transparencia"]:
            endpoints = self.metrics["working_endpoints"].get(api_name, [])
            success_rate = self.metrics["api_success_rates"].get(api_name, 0)
            
            summary_data.append([
                api_name.upper(),
                len(endpoints),
                f"{success_rate:.1f}%",
                ", ".join(endpoints)
            ])
        
        headers = ["API", "Working Endpoints", "Success Rate", "Endpoint Names"]
        return tabulate(summary_data, headers=headers, tablefmt="grid")

    def generate_performance_charts(self, output_dir: str) -> None:
        """
        Generate performance visualization charts
        """
        # Success rates pie chart
        plt.figure(figsize=(10, 6))
        rates = self.metrics["api_success_rates"]
        plt.pie(
            rates.values(),
            labels=rates.keys(),
            autopct='%1.1f%%'
        )
        plt.title("API Success Rates")
        plt.savefig(os.path.join(output_dir, "api_success_rates.png"))
        plt.close()
        
        # Response times box plot
        durations = [
            result["duration"]
            for result in self.results.values()
            if result["status"] == "success"
        ]
        
        plt.figure(figsize=(10, 6))
        plt.boxplot(durations)
        plt.title("API Response Times")
        plt.ylabel("Seconds")
        plt.savefig(os.path.join(output_dir, "api_response_times.png"))
        plt.close()

    def generate_endpoint_documentation(self) -> str:
        """
        Generate detailed endpoint documentation
        """
        doc = []
        doc.append("# Government Procurement API Endpoints Documentation")
        doc.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for api_name, endpoints in config.ENDPOINTS.items():
            doc.append(f"\n## {api_name.upper()} API")
            doc.append("\n### Base URL")
            if api_name == "pncp":
                doc.append(config.PNCP_BASE_URL)
            elif api_name == "comprasgov":
                doc.append(config.COMPRASGOV_BASE_URL)
            else:
                doc.append(config.TRANSPARENCIA_BASE_URL)
            
            doc.append("\n### Endpoints")
            for endpoint_name, url in endpoints.items():
                doc.append(f"\n#### {endpoint_name}")
                doc.append(f"- URL: `{url}`")
                
                # Add example response if available
                for result in self.results.values():
                    if result["status"] == "success":
                        api_results = result["results"].get(api_name, {})
                        endpoint_result = api_results.get(endpoint_name, {})
                        if endpoint_result.get("status") == "working":
                            doc.append("\nExample Response:")
                            doc.append("```json")
                            doc.append(
                                json.dumps(
                                    endpoint_result["sample_data"],
                                    indent=2
                                )
                            )
                            doc.append("```")
                            break
        
        return "\n".join(doc)

    def generate_report(self) -> None:
        """
        Generate comprehensive endpoint report
        """
        logger.info("Generating endpoint report...")
        
        # Create report directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(
            config.EXCEL_CONFIG["output_dir"],
            f"endpoint_report_{timestamp}"
        )
        os.makedirs(report_dir, exist_ok=True)
        
        # Run tests if not already run
        if not self.results:
            self.run_tests()
        
        # Generate report components
        try:
            # Summary report
            summary = [
                "# Endpoint Testing Summary\n",
                f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                f"Total tenders tested: {self.metrics['total_tenders']}",
                f"Successful tests: {self.metrics['successful_tests']}",
                f"Failed tests: {self.metrics['failed_tests']}",
                f"Average response time: {self.metrics['average_duration']:.2f} seconds\n",
                "## API Performance Summary\n",
                self.generate_summary_table()
            ]
            
            with open(os.path.join(report_dir, "summary.md"), "w") as f:
                f.write("\n".join(summary))
            
            # Generate charts
            self.generate_performance_charts(report_dir)
            
            # Generate detailed documentation
            documentation = self.generate_endpoint_documentation()
            with open(os.path.join(report_dir, "endpoint_documentation.md"), "w") as f:
                f.write(documentation)
            
            # Save raw data
            with open(os.path.join(report_dir, "raw_results.json"), "w") as f:
                json.dump(self.results, f, indent=2)
            
            with open(os.path.join(report_dir, "metrics.json"), "w") as f:
                json.dump(self.metrics, f, indent=2)
            
            logger.info(f"Report generated successfully in {report_dir}")
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

def main():
    """
    Main function to generate endpoint report
    """
    try:
        generator = EndpointReportGenerator()
        generator.generate_report()
        logger.info("Report generation completed successfully")
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise

if __name__ == "__main__":
    main()
