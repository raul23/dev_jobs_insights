import os
import sys
# Third-party modules
import ipdb
import numpy as np
# Own modules
from .analyzer import Analyzer
# TODO: module path insertion is hardcoded
sys.path.insert(0, os.path.expanduser("~/PycharmProjects/github_projects"))
from utility.script_boilerplate import LoggingBoilerplate


class IndustriesAnalyzer(Analyzer):
    def __init__(self, conn, db_session, main_config, logging_config):
        # Industries stats to compute
        self.stats_names = ["sorted_industries_count"]
        super().__init__(conn, db_session, main_config, logging_config,
                         self.stats_names)
        sb = LoggingBoilerplate(
            module_name=__name__,
            module_file=__file__,
            cwd=os.getcwd(),
            logging_config=logging_config)
        self.logger = sb.get_logger()

    def run_analysis(self):
        # Reset all industries stats to be computed
        self.reset_stats()
        # Get number of job posts for each industry
        # NOTE: the returned results are sorted in decreasing order of industries'
        # count, i.e. from the most popular industry to the least popular industry
        self._clean_industries_names()
        industries_count = self._count_industries()
        self.logger.debug(
            "There are {} distinct industries".format(len(industries_count)))
        self.logger.debug("There are in total {} industries".format(
            sum(j for i, j in industries_count)))
        self.stats["sorted_industries_count"] = np.array(industries_count)
        self._generate_graphs()

    def _clean_industries_names(self):
        # Standardize the names of the industries
        # NOTE: only the most obvious industries names are standardized. The
        # other less obvious ones are left intact, e.g. 'IT Consulting' could
        # be renamed to 'Consulting' but 'Consulting' is a too broad category
        # and you might lose information doing so.
        # Same for 'Advertising Technology' and 'Advertising'.
        # NOTE: Typos are also fixed
        # NOTE: Some industries should not even be considered as industries
        # e.g. JavaScript, functional programming, facebook, iOS
        # 'and Compliance' seems to be an incomplete name for an industry
        industry_names = {
            'Software Development / Engineering': 'Software Development',
            'eCommerce': 'E-Commerce',
            'Retail - eCommerce': 'E-Commerce',
            'Health Care': 'Healthcare',
            'Fasion': 'Fashion',
            'fintech': 'Financial Technology',
            'blockchain': 'Blockchain',
            'higher': 'Higher Education'
        }
        self.logger.info("Cleaning names of industries")
        for old_name, new_name in industry_names.items():
            sql = "UPDATE industries SET name='{1}' WHERE name='{0}'".format(
                old_name, new_name)
            result = self.db_session.execute(sql)
            self.db_session.commit()
            if result.rowcount > 0:
                self.logger.info(
                    "The industry name '{0}' was changed to '{1}': {2} time{3}".format(
                        old_name, new_name, result.rowcount, 's' if result.rowcount > 1 else ''))
            else:
                self.logger.warning(
                    "The industry name '{0}' couldn't be found".format(old_name))

    def _count_industries(self):
        """
        Returns industries sorted in decreasing order of their occurrences in job posts.
        A list of tuples is returned where a tuple is of the form (industry, count).

        :return: list of tuples of the form (industry, count)
        """
        sql = "SELECT name, COUNT(name) as CountOf from industries GROUP BY name " \
              "ORDER BY CountOf DESC"
        return self.db_session.execute(sql).fetchall()

    # Generate bar chart: industries vs number of job posts
    def _generate_graphs(self):
        # Lazy import. Loading of module takes lots of time. So do it only when
        # needed
        self.logger.info("loading module 'utility.graphutil' ...")
        from utility.graphutil import generate_bar_chart
        self.logger.debug("finished loading module 'utility.graphutil'")
        self.logger.info("Generating bar chart: industries vs number of job posts ...")
        sorted_industries_count = self.stats["sorted_industries_count"]
        bar_chart_industries \
            = self.main_config["graphs_config"]["bar_chart_industries"]
        top_k = self.main_config["graphs_config"]["bar_chart_industries"]["top_k"]
        # TODO: place number (of job posts) on top of each bar
        generate_bar_chart(
            x=sorted_industries_count[:top_k, 0],
            y=sorted_industries_count[:top_k, 1].astype(np.int32),
            xlabel=bar_chart_industries["xlabel"],
            ylabel=bar_chart_industries["ylabel"],
            title=bar_chart_industries["title"].format(top_k))
