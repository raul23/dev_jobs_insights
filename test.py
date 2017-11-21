"""
Data analysis of Stackoverflow developer job posts
"""
import json
import os
import pickle
import sqlite3
import time
import ipdb

import geopy
from geopy.geocoders import Nominatim
from googletrans import Translator
import iso3166
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from mpl_toolkits.basemap import Basemap
import numpy as np
import plotly
from plotly.graph_objs import Scatter, Figure, Layout
# TODO: check if we must use np.{int,float}{32,64}


# TODO: the following variables should be set in a config file
DB_FILENAME = os.path.expanduser("~/databases/jobs_insights.sqlite")
SHAPE_FILENAME = os.path.expanduser("~/data/basemap/st99_d00")
COUNTRIES_FILENAME = "countries_info.json"
US_STATES_FILENAME = "states_hash.json"
TRANSL_COUNTRIES_FILENAME = "cached_transl_countries.json"
CACHED_LOCATIONS_FILENAME = "cached_locations.pkl"
# Number of seconds to wait between two requests to the geocoding service
WAIT_TIME = 1
# The marker to be drawn on a map is scaled by a factor
MARKER_SCALE = 5
# Thresholds for removing salary outliers, i.e. salaries in the range
# [MIN_SALARY, MAX_SALARY] will be included, the rest will be discarded
MIN_MID_RANGE_SALARY_THRESHOLD = 15000
MAX_MID_RANGE_SALARY_THRESHOLD = 400000


class DataAnalyzer:
    def __init__(self, config):
        # Sanity check
        assert "db_filename" in config, "No db_filename provided in config"
        self.conn = create_connection(config["db_filename"])
        # NOTE: `countries` and `us_states` must not be empty when starting the
        # data analysis. However, `translated_countries` can be empty when starting
        # because it will be updated while performing the data analysis; same
        # for `cached_locations`.
        self.countries = load_json(COUNTRIES_FILENAME)
        assert self.countries is not None, "Error in loading countries"
        self.us_states = load_json(US_STATES_FILENAME)
        assert self.us_states is not None, "Error in loading us_states"
        self.translated_countries = load_json(TRANSL_COUNTRIES_FILENAME)
        if self.translated_countries is None:
            self.translated_countries = {}
        self.cached_locations = load_pickle(CACHED_LOCATIONS_FILENAME)
        if self.cached_locations is None:
            self.cached_locations = {}
        # These are all the data that will be saved while performing the various
        # analyses
        # TODO: specify that they are all unique, e.g. no two locations/tags/countries/us states
        # TODO: locations_info is a dict and the rest are np.array
        self.locations_info = None
        self.sorted_tags_count = None
        self.sorted_countries_count = None
        self.sorted_us_states_count = None
        # TODO: {min, max}_salaries might not be used much
        self.min_salaries = None
        self.max_salaries = None
        self.job_ids_with_salary = None
        self.job_id_to_salary_mid_ranges = None
        # Global stats about salary
        self.global_mean_salary = None
        self.global_std_salary = None
        self.global_min_salary = None
        self.global_max_salary = None
        self.min_job_id = None
        self.max_job_id = None
        self.sorted_salary_mid_ranges = None
        # TODO: could not manipulate them as global variables, had the unresolved error
        # in filter_mid_range_salaries()
        self.MIN_MID_RANGE_SALARY_THRESHOLD = MIN_MID_RANGE_SALARY_THRESHOLD
        self.MAX_MID_RANGE_SALARY_THRESHOLD = MAX_MID_RANGE_SALARY_THRESHOLD
        self.avg_mid_range_salaries_by_countries = None
        self.avg_mid_range_salaries_by_us_states = None
        self.avg_mid_range_salaries_by_industries = None
        self.avg_mid_range_salaries_by_roles = None
        self.avg_mid_range_salaries_by_tags = None
        # TODO: the outliers should be removed once and for all as early as possible
        # by finding the corresponding job ids and removing them from the different arrays
        # TODO: rearrange the name of the variables
        self.sorted_industries_count = None

    def run_analysis(self):
        types_of_analysis = ["tags", "locations", "salary", "industries"]
        ipdb.set_trace()
        with self.conn:
            for type in types_of_analysis:
                method_name = "analyze_{}".format(type)
                if method_name in config and config[method_name]:
                    # TODO: sanity check on the method existence
                    analyze_method = self.__getattribute__(method_name)
                    analyze_method()

    def analyze_tags(self):
        """
        Analysis of tags (i.e. technologies such as java, python) which consist in
        ... TODO complete description

        :return:
        """
        # Get counts of tags, i.e. for each tag we want to know its number of
        # occurrences in job posts
        results = self.count_tag_occurrences()
        # NOTE: these are all the tags (even those that don't have a salary
        # associated with) and they are sorted in order of decreasing
        # number of occurrences (i.e. most popular tag at first)
        self.sorted_tags_count = np.array(results)

        # Generate bar chart of tags vs number of job posts
        # TODO: should be set in a config
        top_k = 20
        config = {"x": self.sorted_tags_count[:top_k, 0],
                  "y": self.sorted_tags_count[:top_k, 1].astype(np.int32),
                  "xlabel": "Skills (tags)",
                  "ylabel": "Number of jobs",
                  "title": "Top {} most popular skills".format(top_k),
                  "grid_which": "major"}
        # TODO: place number (of job posts) on top of each bar
        self.generate_bar_chart(config)

    def analyze_locations(self):
        """
        Analysis of locations which consists in ... TODO: complete description

        :return:
        """
        # Get counts of job posts for each location, i.e. for each location we
        # want to know its number of occurrences in job posts
        results = self.count_location_occurrences()
        # Process the results
        self.process_locations(results)
        # TODO: add in config option to set the image dimensions

        # Generate map with markers added on US states that have job posts
        # associated with
        self.generate_map_us_states()
        # Generate map with markers added on countries that have job posts
        # associated with
        self.generate_map_world_countries()
        # Generate map with markers added on european countries that have job
        # posts associated with
        #self.generate_map_europe_countries()

        # NOTE: bar charts are for categorical data
        # Generate bar chart of countries vs number of job posts
        # TODO: should be set in a config
        top_k = 20
        country_names = self.format_country_names(self.sorted_countries_count[:top_k, 0])
        config = {"x": country_names,
                  "y": self.sorted_countries_count[:top_k, 1].astype(np.int32),
                  "xlabel": "Countries",
                  "ylabel": "Number of job posts",
                  "title": "Top {} most popular countries".format(top_k),
                  "grid_which": "both"}
        # TODO: place number (of job posts) on top of each bar
        #self.generate_bar_chart(config)
        # Generate bar chart of US states vs number of job posts
        config = {"x": self.sorted_us_states_count[:, 0],
                  "y": self.sorted_us_states_count[:, 1].astype(np.int32),
                  "xlabel": "US states",
                  "ylabel": "Number of job posts",
                  "title": "US states popularity",
                  "grid_which": "major"}
        #self.generate_bar_chart(config)

        # Generate pie chart of countries vs number of job posts
        config = {"labels": self.sorted_countries_count[:, 0],
                  "values": self.sorted_countries_count[:, 1].astype(np.int32),
                  "title": "Countries popularity by % of job posts"}
        # TODO: add 'other countries' for countries with few job posts
        # Pie chart is too crowded for countries with less than 0.9% of job posts
        self.generate_pie_chart(config)
        # Generate pie chart of countries vs number of job posts
        config = {"labels": self.sorted_us_states_count[:, 0],
                  "values": self.sorted_us_states_count[:, 1].astype(np.int32),
                  "title": "US States popularity by % of job posts"}
        #self.generate_pie_chart(config)

    def analyze_salary_by_locations(self):
        # Get location names that have a salary associated with
        results = self.select_locations(tuple(self.job_ids_with_salary))
        # Sanity check on results
        assert len(results) == len(self.job_ids_with_salary), \
            "job ids are missing in returned results"
        # Process results to extract average mid-range salaries for each
        # countries and US states
        self.process_locations_with_salaries(results)

    def analyze_salary_by_topic(self, topic):
        # Sanity check on input `topic`
        assert topic in ["locations", "industries", "roles", "tags"], \
            "'{}' is not a valid topic".format(topic)
        # Get topic's rows that have a salary associated with
        # TODO: add sanity check on the select method/process, what if they don't
        # exist, we should skip the topic and report an error
        select_method = self.__getattribute__("select_{}".format(topic))
        # TODO: remove eval
        #select_method = eval("self.select_{}".format(topic))
        process_results_method = self.__getattribute__("process_{}_with_salaries".format(topic))
        # TODO: remove eval
        #process_results_method = eval("self.process_{}_with_salaries".format(topic))
        results = select_method(tuple(self.job_ids_with_salary))
        # Process results to extract average mid-range salaries for each topic's rows
        process_results_method(results, topic)

    def analyze_salary(self):
        # Compute salary mid-range for each min-max interval
        self.compute_salary_mid_ranges()
        # Compute global stats on salaries, e.g. global max/min mid-range salaries
        self.compute_global_stats()

        # Analyze salary by different topics
        # TODO: see if you can divide locations into countries and us_states
        topics = ["locations", "industries", "roles", "tags"]
        for topic in topics:
            self.analyze_salary_by_topic(topic)

        # Generate histogram of salary mid ranges vs number of job posts
        # TODO: you can use self.MAX_MID_RANGE_SALARY_THRESHOLD only after running
        # compute_global_stats() where the global max and min salaries are computed
        config = {"data": self.filter_mid_range_salaries(),
                  "bins": np.arange(0, self.MAX_MID_RANGE_SALARY_THRESHOLD, 10000),
                  "xlabel": "Mid-range salaries",
                  "ylabel": "Number of job posts",
                  "title": "Histogram: Mid-range salaries",
                  "grid_which": "major",
                  "xaxis_major_mutiplelocator": 10000,
                  "xaxis_minor_mutiplelocator": 1000,
                  "yaxis_major_mutiplelocator": 5,
                  "yaxis_minor_mutiplelocator": 1
                  }
        #self.generate_histogram(config)

        # Generate scatter plots of number of job posts vs average mid-range salary
        # for each topic (e.g. locations, roles)
        config = {"x": None,
                  "y": None,
                  "mode": "markers",
                  "text": None,
                  "title": "",
                  "yaxis_tickformat": "$0.0f"
                  }
        # TODO: the topics should be set in the constructor
        topics = ["countries", "us_states", "industries", "roles", "tags"]
        titles = ["countries", "US states", "industries", "job roles", "programming skills"]
        # Sanity check on topics and corresponding titles
        assert len(topics) == len(titles),\
            "Number of topics ({}) and titles ({}) don't match".format(len(topics), len(titles))
        # Build complete title
        titles = ["Average mid-range salary of "+title for title in titles]
        topic_to_title = dict(zip(topics, titles))
        for topic, title in topic_to_title.items():
            # TODO: add sanity check on eval(), i.e. make sure that the data array
            # exists before using it
            data = self.__getattribute__("avg_mid_range_salaries_by_{}".format(topic))
            # TODO: sanity check on data["average_mid_range_salary"], do the sanity
            # check within filter_data()
            indices = self.filter_data(data["average_mid_range_salary"],
                                       min_threshold=self.MIN_MID_RANGE_SALARY_THRESHOLD,
                                       max_threshold=self.MAX_MID_RANGE_SALARY_THRESHOLD)
            # TODO: sanity check on data keys
            # Filter the arrays to keep only the filtered data
            config["x"] = data["count"][indices]
            config["y"] = data["average_mid_range_salary"][indices]
            config["text"] = data[topic][indices]
            config["title"] = title
            self.generate_scatter_plot(config)

    def analyze_industries(self):
        """
        Analysis of tags (i.e. technologies such as java, python) which consist in
        ... TODO complete description

        :return:
        """
        # Get number of job posts for each industry
        # TODO: specify that the results are already sorted in decreasing order of industry's count, i.e.
        # from the most popular industry to the least one
        results = self.count_industry_occurrences()
        # TODO: Process the results by summing the similar industries (e.g. Software Development with
        # Software Development / Engineering or eCommerce with E-Commerce)
        # TODO: use Software Development instead of the longer Software Development / Engineering
        self.sorted_industries_count = np.array(results)

        # Generate bar chart: industries vs number of job posts
        top_k = 20
        config = {"x": self.sorted_industries_count[:top_k, 0],
                  "y": self.sorted_industries_count[:top_k, 1].astype(np.int32),
                  "xlabel": "Industries",
                  "ylabel": "Number of jobs",
                  "title": "Top {} most popular industries".format(top_k),
                  "grid_which": "major"}
        # TODO: place number (of job posts) on top of each bar
        self.generate_bar_chart(config)

    def compute_salary_mid_ranges(self):
        # Get list of min/max salary, i.e. for each job id we want its
        # corresponding min/max salary
        # TODO: return the min/max salaries in ascending order so you don't have
        # to sort `salary_mid_ranges` later on. You will have to modify the SQL
        # SELECT request in `select_all_min_salaries()` and `select_all_max_salaries()`
        # TODO: check if there are other cases where you could sort the data at the source
        # instead of doing it here after retrieving the data from the db
        job_ids_1, min_salaries = self.get_salaries("min")
        job_ids_2, max_salaries = self.get_salaries("max")
        self.min_salaries = min_salaries
        self.max_salaries = max_salaries
        # Sanity check on `job_ids_*`
        assert np.array_equal(job_ids_1, job_ids_2), "The two returned job_ids don't match"
        self.job_ids_with_salary = job_ids_1
        del job_ids_2

        # Compute salary mid-range for each min-max interval
        salary_ranges = np.hstack((min_salaries, max_salaries))
        # TODO: check precision for `salary_mid_ranges`
        salary_mid_ranges = salary_ranges.mean(axis=1)
        self.job_id_to_salary_mid_ranges = dict(zip(self.job_ids_with_salary, salary_mid_ranges))
        sorted_indices = np.argsort(salary_mid_ranges)
        self.sorted_salary_mid_ranges = salary_mid_ranges[sorted_indices]
        # Get job_id's associated with these global min and max salaries
        min_index = sorted_indices[0]
        max_index = sorted_indices[-1]
        self.min_job_id = self.job_ids_with_salary[min_index]
        self.max_job_id = self.job_ids_with_salary[max_index]

    def compute_global_stats(self):
        # Compute salary mean across list of mid-range salaries
        global_mean_salary = self.sorted_salary_mid_ranges.mean()
        # Precision to two decimals
        self.global_mean_salary = float(format(global_mean_salary, '.2f'))
        # Compute std across list of mid-range salaries
        global_std_salary = self.sorted_salary_mid_ranges.std()
        # Precision to two decimals
        self.global_std_salary = float(format(global_std_salary, '.2f'))
        # Get min and max salaries across list of mid-range salaries
        self.global_min_salary = self.sorted_salary_mid_ranges[0]
        self.global_max_salary = self.sorted_salary_mid_ranges[-1]

    def get_salaries(self, which="min"):
        if which == "min":
            salaries = self.select_all_min_salaries()
        else:
            salaries = self.select_all_max_salaries()
        salaries = np.array(salaries)
        # Extract the job ids
        job_ids = salaries[:, 0]
        # Extract the corresponding min salaries
        salaries = salaries[:, 1].astype(np.float64)
        # Reshape salaries arrays
        salaries = salaries.reshape((len(salaries), 1))
        return job_ids, salaries

    def format_country_names(self, country_names, max_n_char=20):
        for i, name in enumerate(country_names):
            if len(name) > max_n_char:
                alpha2 = self.countries[name]["alpha2"]
                country_names[i] = alpha2
        return country_names

    def count_tag_occurrences(self):
        """
        Returns tags sorted in decreasing order of their occurrences in job posts.
        A list of tuples is returned where a tuple is of the form (tag_name, count).

        :return: list of tuples of the form (tag_name, count)
        """
        sql = '''SELECT name, COUNT(name) as CountOf FROM entries_tags GROUP BY name ORDER BY CountOf DESC'''
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def count_location_occurrences(self):
        """
        Returns locations sorted in decreasing order of their occurrences in job posts.
        A list of tuples is returned where a tuple is of the form (location, count).

        :return: list of tuples of the form (location, count)
        """
        sql = '''SELECT location, COUNT(*) as CountOf FROM job_posts GROUP BY location ORDER BY CountOf DESC'''
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def count_industry_occurrences(self):
        """
        Returns industries sorted in decreasing order of their occurrences in job posts.
        A list of tuples is returned where a tuple is of the form (industry, count).

        :return: list of tuples of the form (industry, count)
        """
        sql = '''SELECT value, COUNT(*) as CountOf from job_overview WHERE name='Industry' GROUP BY value ORDER BY CountOf DESC'''
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def select_all_min_salaries(self):
        """
        Returns all minimum salaries.
        A list of tuples is returned where a tuple is of the form (job_id, min_salary).

        :return: list of tuples of the form (job_id, min_salary)
        """
        sql = """SELECT job_id, value FROM job_salary WHERE name LIKE 'min%'"""
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def select_all_max_salaries(self):
        """
        Returns all maximum salaries.
        A list of tuples is returned where a tuple is of the form (job_id, max_salary).

        :return: list of tuples of the form (job_id, max_salary)
        """
        sql = """SELECT job_id, value FROM job_salary WHERE name LIKE 'max%'"""
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def select_locations(self, job_ids):
        # Sanity check on input
        # TODO: remove too much info in assert message, i.e. the name of the method
        assert type(job_ids) is tuple, "job_ids is not a tuple"
        sql = '''SELECT id, location FROM job_posts WHERE id IN ({})'''
        sql = self.build_sql_request(sql, len(job_ids))
        cur = self.conn.cursor()
        cur.execute(sql, job_ids)
        return cur.fetchall()

    def select_industries(self, job_ids):
        # Sanity check on input
        assert type(job_ids) is tuple, "job_ids is not a tuple"
        sql = '''SELECT job_id, value FROM job_overview WHERE job_id IN ({}) AND name="Industry"'''
        sql = self.build_sql_request(sql, len(job_ids))
        cur = self.conn.cursor()
        cur.execute(sql, job_ids)
        return cur.fetchall()

    def select_roles(self, job_ids):
        # Sanity check on input
        assert type(job_ids) is tuple, "job_ids is not a tuple"
        sql = '''SELECT job_id, value FROM job_overview WHERE job_id IN ({}) AND name="Role"'''
        sql = self.build_sql_request(sql, len(job_ids))
        cur = self.conn.cursor()
        cur.execute(sql, job_ids)
        return cur.fetchall()

    def select_tags(self, job_ids):
        # Sanity check on input
        assert type(job_ids) is tuple, "job_ids is not a tuple"
        sql = '''SELECT * FROM entries_tags WHERE id IN ({})'''
        sql = self.build_sql_request(sql, len(job_ids))
        cur = self.conn.cursor()
        cur.execute(sql, job_ids)
        return cur.fetchall()

    @staticmethod
    # TODO: rename it to add_sql_placeholders
    def build_sql_request(sql, n_items):
        placeholders = list(n_items * "?")
        placeholders = str(placeholders)
        placeholders = placeholders.replace("[", "")
        placeholders = placeholders.replace("]", "")
        placeholders = placeholders.replace("'", "")
        return sql.format(placeholders)

    def process_locations(self, locations):
        # Temp dicts
        locations_info = {}
        countries_to_count = {}
        us_states_to_count = {}
        # TODO: factorization of for loop with generate_map()
        for (i, (location, count)) in enumerate(locations):
            print("[{}/{}]".format((i + 1), len(locations)))
            # Check if valid location
            if not is_valid_location(location):
                # NOTE: We ignore the case where `location` is empty (None)
                # or refers to "No office location"
                # TODO: add logging
                continue
            # Sanitize input: this should be done at the source, i.e. in the
            # script that is loading data into the database
            elif ";" in location:
                new_locations = location.split(";")
                for new_loc in new_locations:
                    locations.append((new_loc.strip(), 1))
                continue
            else:
                # Get country or US state from `location`
                last_part_loc = get_last_part_loc(location)
                # Sanity check
                assert last_part_loc is not None, "last_part_loc is None"
                # Is the location referring to a country or a US state?
                if self.is_a_us_state(last_part_loc):
                    # `location` refers to a US state
                    # Save last part of `location` and its count (i.e. number of
                    # occurrences in job posts)
                    us_states_to_count.setdefault(last_part_loc, 0)
                    us_states_to_count[last_part_loc] += count
                    # Also since it is a US state, save 'United States' and its
                    # count (i.e. number of occurrences in job posts)
                    # NOTE: in the job posts, the location for a US state is
                    # given without the country at the end, e.g. Fort Meade, MD
                    countries_to_count.setdefault("United States", 0)
                    countries_to_count["United States"] += count
                    # Add ', United States' at the end of `location` since the
                    # location for US states in job posts don't specify the country
                    # and we might need this extra info when using the geocoding
                    # service to retrieve map coordinates to distinguish places
                    # from Canada and USA that might have the similar name for
                    # the location
                    # Example: 'Westlake Village, CA' might get linked to
                    # 'Westlake Village, Hamlet of Clairmont, Grande Prairie, Alberta'
                    # In this case, it should be linked to a region in California,
                    # not in Canada
                    formatted_location = "{}, United States".format(location)
                    locations_info.setdefault(formatted_location, {"country": "United States",
                                                         "count": 0})
                    locations_info[formatted_location]["count"] += count
                else:
                    # `location` refers to a country
                    # Check for countries written in other languages, and keep
                    # only the english translation
                    # NOTE: sometimes, a country is not given in English e.g.
                    # Deutschland and Germany
                    # Save the location and its count (i.e. number of occurrences
                    # in job posts)
                    transl_country = self.get_english_country_transl(last_part_loc)
                    assert transl_country in self.countries, "The country '{}' is not found".format(transl_country)
                    countries_to_count.setdefault(transl_country, 0)
                    countries_to_count[transl_country] += count
                    locations_info.setdefault(location, {"country": transl_country,
                                                         "count": 0})
                    locations_info[location]["count"] += count
        # NOTE: `locations_info` is already sorted based on the location's count
        # because it is almost a copy of `locations` which is already sorted
        # (based on the location's count) from the returned database request
        self.locations_info = locations_info
        # Sort the countries and US-states dicts based on the number of
        # occurrences, i.e. the dict's values. And convert the sorted dicts
        # into a numpy array
        # TODO: check if these are useful arrays
        self.sorted_countries_count = sorted(countries_to_count.items(), key=lambda x: x[1], reverse=True)
        self.sorted_countries_count = np.array(self.sorted_countries_count)
        self.sorted_us_states_count = sorted(us_states_to_count.items(), key=lambda x: x[1], reverse=True)
        self.sorted_us_states_count = np.array(self.sorted_us_states_count)

    def process_locations_with_salaries(self, locations, topic):
        # Temp dicts
        countries_to_salary = {}
        us_states_to_salary = {}
        # TODO: factorization of for loop with process_locations() and generate_map()
        # However, the other cases use (i, (location, count)) in the for loop, maybe
        # only the other two will be factorized
        for (i, (job_id, location)) in enumerate(locations):
            print("[{}/{}]".format((i + 1), len(locations)))
            # Check if valid location
            if not is_valid_location(location):
                # NOTE: We ignore the case where `location` is empty (None)
                # or refers to "No office location"
                # TODO: add logging
                continue
            # Sanitize input: this should be done at the source, i.e. in the
            # script that is loading data into the database
            elif ";" in location:
                ipdb.set_trace()
                # TODO: it should be done in a separate method since we are also
                # doing the same thing in process_locations()
                new_locations = location.split(";")
                for new_loc in new_locations:
                    locations.append((new_loc.strip(), 1))
                continue
            else:
                # Get country or US state from `location`
                last_part_loc = get_last_part_loc(location)
                # Sanity check
                assert last_part_loc is not None, "last_part_loc is None"
                # Is the location referring to a country or a US state?
                if self.is_a_us_state(last_part_loc):
                    # `location` refers to a US state
                    # Save last part of `location` along with some data for
                    # computing the average mid-range salary for the given US state
                    self.add_salary(us_states_to_salary, last_part_loc, job_id)
                    # Also since it is a US state, save 'United States' along with
                    # some data for computing the average mid-range salary for
                    # the given US country
                    # NOTE: in the job posts, the location for a US state is
                    # given without the country at the end, e.g. Fort Meade, MD
                    self.add_salary(countries_to_salary, "United States", job_id)
                else:
                    # `location` refers to a country
                    # Check for countries written in other languages, and keep
                    # only the english translation
                    # NOTE: sometimes, a country is not given in English e.g.
                    # Deutschland and Germany
                    # Save the location and along with some data for computing
                    # the average mid-range salary for the given country
                    transl_country = self.get_english_country_transl(last_part_loc)
                    assert transl_country in self.countries, \
                        "The country '{}' is not found".format(transl_country)
                    self.add_salary(countries_to_salary, transl_country, job_id)
        # For each dict, keep every fields, except "cumulative_sum" and build
        # a structured array out of the dicts
        # TODO: use a structured array like the following, so you can have columns
        # in a numpy array with different data types, and also it is easier to sort
        # this kind of array based on the name of a field
        # TODO: factorization: same as in process_topic_with_salaries and
        # countries and us_states same code
        temp_countries = [(k, v["average_mid_range_salary"], v["count"])
                          for k, v in countries_to_salary.items()]
        temp_us_states = [(k, v["average_mid_range_salary"], v["count"])
                          for k, v in us_states_to_salary.items()]
        # Fields (+data types) for the structured array
        # TODO: use the input `topic` to label the fields, call the method twice for
        # countries and us_states
        dtype = [("countries", "S20"), ("average_mid_range_salary", float), ("count", int)]
        temp_countries = np.array(temp_countries, dtype=dtype)
        dtype = [("us_states", "S10"), ("average_mid_range_salary", float), ("count", int)]
        temp_us_states = np.array(temp_us_states, dtype=dtype)
        # Sort each array based on the field 'average_mid_range_salary' and in
        # descending order of the given field
        temp_countries.sort(order="average_mid_range_salary")
        temp_us_states.sort(order="average_mid_range_salary")
        temp_countries = temp_countries[::-1]
        temp_us_states = temp_us_states[::-1]
        self.avg_mid_range_salaries_by_countries = temp_countries
        self.avg_mid_range_salaries_by_us_states = temp_us_states

    def process_industries_with_salaries(self, industries, topic):
        self.avg_mid_range_salaries_by_industries = self.process_topic_with_salaries(industries, topic)

    def process_roles_with_salaries(self, roles, topic):
        self.avg_mid_range_salaries_by_roles = self.process_topic_with_salaries(roles, topic)

    def process_tags_with_salaries(self, tags, topic):
        self.avg_mid_range_salaries_by_tags = self.process_topic_with_salaries(tags, topic)

    def process_topic_with_salaries(self, input_data, topic_name):
        topic_to_salary = {}
        for job_id, name in input_data:
            self.add_salary(topic_to_salary, name, job_id)
        # Keep every fields, except "cumulative_sum" and build a structured array
        # out of the dict
        struct_arr = [(k, v["average_mid_range_salary"], v["count"])
                      for k, v in topic_to_salary.items()]
        # Fields (+data types) for the structured array
        # TOOD: adjust precision of float numbers
        # TODO: the length of the string field should be set in a config (for each topic?)
        dtype = [(topic_name, "S30"), ("average_mid_range_salary", float), ("count", int)]
        struct_arr = np.array(struct_arr, dtype=dtype)
        # Sort the array based on the field 'average_mid_range_salary' and in
        # descending order of the given field
        struct_arr.sort(order="average_mid_range_salary")
        struct_arr = struct_arr[::-1]
        return struct_arr

    def add_salary(self, dictionary, name, job_id):
        dictionary.setdefault(name, {"average_mid_range_salary": 0,
                                     "cumulative_sum": 0,
                                     "count": 0})
        mid_range_salary = self.job_id_to_salary_mid_ranges[job_id]
        dictionary[name]["count"] += 1  # update count
        cum_sum = dictionary[name]["cumulative_sum"]
        dictionary[name]["average_mid_range_salary"] \
            = (cum_sum + mid_range_salary) / dictionary[name]["count"]  # update average
        dictionary[name]["cumulative_sum"] += mid_range_salary  # update cumulative sum

    def filter_locations(self, include_continents="All", exclude_countries=None):
        # TODO: Sanity check on `include_continents` and `exclude_countries`
        filtered_locations = []
        for loc, country_info in self.locations_info.items():
            country = country_info["country"]
            count = country_info["count"]
            if (include_continents == "All" or self.get_continent(country) in include_continents) \
                    and (exclude_countries is None or country not in exclude_countries):
                filtered_locations.append((loc, count))
        return filtered_locations

    # TODO: it is better to return the indices of salaries to keep; thus use
    # the filter_data() method instead which can filter any kind of data, not only
    # salaries but also counts for instance
    def filter_mid_range_salaries(self):
        # TODO: change all *salary_mid_ranges* to *mid_range_salaries*,
        # even methods
        # Sanity check on the salary thresholds
        max_salary = self.sorted_salary_mid_ranges.max()
        min_salary = self.sorted_salary_mid_ranges.min()
        # Sanity check on mid-range salary thresholds
        # TODO: these checks should be done when computing the global max and min in compute_global_stats()
        if not (max_salary >= self.MIN_MID_RANGE_SALARY_THRESHOLD >= min_salary):
            self.MIN_MID_RANGE_SALARY_THRESHOLD = min_salary
        if not (max_salary >= self.MAX_MID_RANGE_SALARY_THRESHOLD >= min_salary):
            self.MAX_MID_RANGE_SALARY_THRESHOLD = max_salary
        first_cond = (self.sorted_salary_mid_ranges >= self.MIN_MID_RANGE_SALARY_THRESHOLD)
        second_cond = (self.sorted_salary_mid_ranges <= self.MAX_MID_RANGE_SALARY_THRESHOLD)
        return self.sorted_salary_mid_ranges[first_cond & second_cond]

    def filter_data(self, data, min_threshold, max_threshold):
        # Sanity check on input thresholds
        if not (data.max() >= min_threshold >= data.min()):
            min_threshold = data.min()
        if not (data.max() >= max_threshold >= data.min()):
            max_threshold = data.max()
        first_cond = data >= min_threshold
        second_cond = data <= max_threshold
        return np.where(first_cond & second_cond)

    @staticmethod
    def generate_scatter_plot(plt_config):
        # TODO: add labels to axes
        default_config = {"x": None,
                          "y": None,
                          "mode": "markers",
                          "text": None,
                          "title": "",
                          "hovermode": "closest",
                          "yaxis_tickformat": "$0.0f"
                          }
        # Sanity check on config dicts
        assert len(default_config) >= len(plt_config), \
            "plt_config has {} keys and default_config has {} keys".format(len(plt_config), len(default_config))
        default_config.update(plt_config)
        plt_config = default_config
        x = plt_config["x"]
        y = plt_config["y"]
        mode = plt_config["mode"]
        text = plt_config["text"]
        title = plt_config["title"]
        hovermode = plt_config["hovermode"]
        yaxis_tickformat = plt_config["yaxis_tickformat"]
        assert type(x) == type(np.array([])), "wrong type on input array 'x'"
        assert type(y) == type(np.array([])), "wrong type on input array 'y'"
        assert type(text) == type(np.array([])), "wrong type on input array 'text'"
        plotly.offline.plot({
            "data": [Scatter(x=list(x.flatten()),
                             y=list(y.flatten()),
                             mode=mode,
                             text=list(text.flatten()))],
            "layout": Layout(title=title, hovermode=hovermode,
                             yaxis=dict(tickformat=yaxis_tickformat))
        })

    @staticmethod
    def generate_histogram(plt_config):
        default_config = {"data": None,
                          #"bin_width": 10000, # TODO: not used
                          "bins": None,
                          "xlabel": "",
                          "ylabel": "",
                          "title": "",
                          "grid_which": "major",
                          "xaxis_major_mutiplelocator": 10000,
                          "xaxis_minor_mutiplelocator": 1000,
                          "yaxis_major_mutiplelocator": 5,
                          "yaxis_minor_mutiplelocator": 1
                          }
        # Sanity check on config dicts
        assert len(default_config) >= len(plt_config), \
            "plt_config has {} keys and default_config has {} keys".format(len(plt_config), len(default_config))
        default_config.update(plt_config)
        plt_config = default_config
        data = plt_config["data"]
        bins = plt_config["bins"]
        #bin_width = plt_config["bin_width"] # TODO: not used
        xlabel = plt_config["xlabel"]
        ylabel = plt_config["ylabel"]
        title = plt_config["title"]
        grid_which = plt_config["grid_which"]
        xaxis_major_mutiplelocator = plt_config["xaxis_major_mutiplelocator"]
        xaxis_minor_mutiplelocator = plt_config["xaxis_minor_mutiplelocator"] # TODO: not used
        yaxis_major_mutiplelocator = plt_config["yaxis_major_mutiplelocator"]
        yaxis_minor_mutiplelocator = plt_config["yaxis_minor_mutiplelocator"]
        # Sanity check on the input array
        assert type(data) == type(np.array([])), "wrong type on input array 'data'"
        assert grid_which in ["minor", "major", "both"], \
            "wrong value for grid_which='{}'".format(grid_which)
        #n_bins = np.ceil((data.max() - data.min()) / bin_width).astype(np.int64)
        ax = plt.gca()
        ax.hist(data, bins=bins, color="r")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(xaxis_major_mutiplelocator))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(yaxis_major_mutiplelocator))
        ax.yaxis.set_minor_locator(ticker.MultipleLocator(yaxis_minor_mutiplelocator))
        plt.xlim(0, data.max())
        labels = ax.get_xticklabels()
        plt.setp(labels, rotation=270.)
        plt.grid(True, which="major")
        plt.tight_layout()
        # TODO: add function to save image instead of showing it
        plt.show()

    def generate_map_us_states(self):
        # TODO: find out the complete name of the map projection used
        # We are using the Lambert ... map projection and cropping the map to
        # display only the USA territory
        map = Basemap(llcrnrlon=-119, llcrnrlat=22, urcrnrlon=-64, urcrnrlat=49,
                      projection='lcc', lat_1=32, lat_2=45, lon_0=-95)
        map.readshapefile(SHAPE_FILENAME, name="states", drawbounds=True)
        locations = self.filter_locations(include_continents=["North America"],
                                          exclude_countries=["Canada", "Mexico"])
        self.generate_map(map, locations,
                          markersize=lambda count: int(np.sqrt(count)) * MARKER_SCALE,
                          top_k=3)

    def generate_map_world_countries(self):
        # a Miller Cylindrical projection
        # TODO: should be set in the config, just like MARKER_SCALE which is used
        # in generate_map_us_states()
        marker_scale = 1.5
        map = Basemap(projection="mill",
                      llcrnrlon=-180., llcrnrlat=-60,
                      urcrnrlon=180., urcrnrlat=80.)
        # Draw coast lines, countries, and fill the continents
        map.drawcoastlines()
        map.drawcountries()
        map.drawstates()
        map.fillcontinents()
        map.drawmapboundary()
        locations = self.filter_locations(include_continents="All")
        self.generate_map(map, locations, markersize=lambda count: marker_scale)

    def generate_map_europe_countries(self):
        pass

    def generate_map(self, map, locations, markersize, top_k=None):
        new_cached_locations = False
        top_k_locations = []
        if top_k is not None:
            top_k_locations = get_top_k_locations(locations, k=top_k)
        for (i, (location, count)) in enumerate(locations):
            print("[{}/{}]".format((i+1), len(locations)))
            # Check if valid location
            if not is_valid_location(location):
                # NOTE: We ignore the cases where `location` is empty (None)
                # or refers to "No office location" or is not in the right continent
                # TODO: add logging
                continue
            # Check if we already computed the location's longitude and latitude
            # with the geocoding service
            elif location in self.cached_locations:
                loc = self.cached_locations[location]
            else:
                # TODO: else clause to be checked
                ipdb.set_trace()
                # Get the location's longitude and latitude
                # We are using the module `geopy` to get the longitude and latitude of
                # locations which will then be transformed into map coordinates so we can
                # draw markers on a map with `basemap`
                geolocator = Nominatim()
                loc = None
                try:
                    loc = geolocator.geocode(location)
                except geopy.exc.GeocoderTimedOut:
                    ipdb.set_trace()
                    dump_pickle(self.cached_locations, CACHED_LOCATIONS_FILENAME)
                    # TODO: do something when there is a connection error with the geocoding service
                # Check if the geocoder service was able to provide the map coordinates
                if loc is None:
                    ipdb.set_trace()
                    # Take the last part (i.e. country) since the whole location
                    # string is not recognized by the geocoding service
                    last_part_loc = get_last_part_loc(location)
                    # Sanity check
                    assert last_part_loc is not None, "last_part_loc is None"
                    time.sleep(WAIT_TIME)
                    loc = geolocator.geocode(last_part_loc)
                    assert loc is not None, "The geocoding service could not for the second time" \
                                            "provide the map coordinates for the location '{}'".format(last_part_loc)
                time.sleep(WAIT_TIME)
                new_cached_locations = True
                assert loc is not None, "loc is None"
                self.cached_locations[location] = loc
            # Transform the location's longitude and latitude to the projection
            # map coordinates
            x, y = map(loc.longitude, loc.latitude)
            # Plot the map coordinates on the map; the size of the marker is
            # proportional to the number of occurrences of the location in job posts
            map.plot(x, y, marker="o", color="Red", markersize=markersize(count))
            # Annotate topk locations, i.e.the topk locations with the most job posts
            if location in top_k_locations:
                plt.text(x, y, location, fontsize=5, fontweight="bold",
                         ha="left", va="bottom", color="k")
        # Dump `cached_locations` as a pickle file if new locations' map
        # coordinates computed
        if new_cached_locations:
            dump_pickle(self.cached_locations, CACHED_LOCATIONS_FILENAME)
        plt.show()

    @staticmethod
    def generate_bar_chart(plt_config):
        default_config = {"x": None,
                          "y": None,
                          "xlabel": "",
                          "ylabel": "",
                          "title": "",
                          "grid_which": "major",
                          "yaxis_major_mutiplelocator": 20,
                          "yaxis_minor_mutiplelocator": 10}
        # Sanity check on config dicts
        assert len(default_config) >= len(plt_config), "generate_bar_chart(): plt_config" \
                                                       "has {} keys and default_config has {} keys".format(len(plt_config), len(default_config))
        default_config.update(plt_config)
        plt_config = default_config
        x = plt_config["x"]
        y = plt_config["y"]
        xlabel = plt_config["xlabel"]
        ylabel = plt_config["ylabel"]
        title = plt_config["title"]
        grid_which = plt_config["grid_which"]
        # Sanity check on the input arrays
        assert type(x) == type(np.array([])), "generate_bar_chart(): wrong type on input array 'x'"
        assert type(y) == type(np.array([])), "generate_bar_chart(): wrong type on input array 'y'"
        assert x.shape == y.shape, "generate_bar_chart(): wrong shape with 'x' and 'y'"
        assert grid_which in ["minor", "major", "both"], "generate_bar_chart(): " \
                                                         "wrong value for grid_which='{}'".format(grid_which)
        ax = plt.gca()
        index = np.arange(len(x))
        plt.bar(index, y)
        plt.xticks(index, x)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        labels = ax.get_xticklabels()
        plt.setp(labels, rotation=270.)
        ax.yaxis.set_major_locator(ticker.MultipleLocator(plt_config["yaxis_major_mutiplelocator"]))
        ax.yaxis.set_minor_locator(ticker.MultipleLocator(plt_config["yaxis_minor_mutiplelocator"]))
        #plt.minorticks_on()
        plt.grid(which=grid_which)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def generate_pie_chart(plt_config):
        default_config = {"values": None,
                          "labels": None,
                          "title": ""}
        # Sanity check on config dicts
        assert len(default_config) >= len(plt_config), \
            "plt_config has {} keys and default_config has {} keys".format(len(plt_config), len(default_config))
        default_config.update(plt_config)
        values = plt_config["values"]
        labels = plt_config["labels"]
        title = plt_config["title"]
        # Sanity check on the input arrays
        assert isinstance(values, type(np.array([]))), "Wrong type on input array 'values'"
        assert isinstance(labels, type(np.array([]))), "Wrong type on input array 'labels'"
        assert values.shape == labels.shape, "Wrong shape with 'labels' and 'values'"
        ax = plt.gca()
        plt.pie(values, labels=labels, autopct="%1.1f%%")
        ax.set_title(title)
        plt.axis("equal")
        plt.show()

    def generate_report(self):
        pass

    def is_a_us_state(self, location):
        """
        Returns True if the location refers to a US state and False otherwise.

        NOTE: we assume that the locations in Stackoverflow job posts provide two
        letters for US states only (except for UK) but it is good enough for our
        needs

        :param location: string of the location to check
        :return bool: True if it is a US state or False otherwise
        """
        # Sanity check to make sure it is not a raw location directly retrieved
        # from the database
        assert location.find(",") == -1, "The location ({}) given to is_a_us_state() " \
                                         "contains a comma"
        # NOTE: the location can refer to a country (e.g. Seongnam-si, South Korea)
        # or a US state (e.g. Portland, OR). Usually, if the last part of the
        # location string consists of two capital letters, it refers to a US
        # state; however we must take into account 'UK'
        if location != "UK" and len(location) == 2:
            if location in self.us_states:
                return True
            else:
                raise KeyError("The two-letters location '{}' is not recognized"
                               "as a US state".format(location))
        else:
            return False

    def get_english_country_transl(self, country):
        """
        Returns the translation of a country in english

        NOTE: in the Stackoverflow job posts, some countries are not provided in
        English and we must only work with their english translations

        :return:
        """
        # TODO: countries not found: UK (it is found as UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND),
        # South Korea (it is found as REPUBLIC OF KOREA), IRAN (it is found as REPUBLIC OF IRAN)
        if country in self.countries:
            return country
        elif country in self.translated_countries:
            return self.translated_countries[country]
        else:
            # TODO: google translation service has problems with Suisse->Suisse
            translator = Translator()
            transl_country = translator.translate(country, dest='en').text
            # Save the translation
            temp = {country: transl_country}
            self.translated_countries.update(temp)
            dump_json(temp, TRANSL_COUNTRIES_FILENAME, update=True)
            return transl_country

    def get_continent(self, country):
        assert country is not None, "country is None in get_continent()"
        if country in self.countries:
            return self.countries[country]["continent"]
        else:
            # TODO: test else clause
            ipdb.set_trace()
            return None


def get_top_k_locations(locations, k):
    assert type(locations) == list, "get_top_k_locations(): locations must be a list of tuples"
    locations = np.array(locations)
    count = locations[:, 1].astype(np.int32)
    sorted_indices = np.argsort(count)[::-1]
    return locations[sorted_indices][:k]


def load_json(path):
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        print(e)
        return None
    return data


def dump_json(data, path, update=False):
    def dump_data(data, path):
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except FileNotFoundError as e:
            print(e)
            return None
        return 0
    if os.path.isfile(path) and update:
        retval = load_json(path)
        if retval is None:
            return None
        else:
            assert type(data) == dict, "Type of '{}' is not a dict".format(data)
            retval.update(data)
            return dump_data(retval, path)
    else:
        return dump_data(data, path)


# TODO: utility function
def create_connection(db_file, autocommit=False):
    """
    Creates a database connection to the SQLite database specified by the db_file

    :param db_file: database file
    :param autocommit: TODO
    :return: sqlite3.Connection object  or None
    """
    try:
        if autocommit:
            conn = sqlite3.connect(db_file, isolation_level=None)
        else:
            conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)

    return None


# TODO: add in Utility
def load_pickle(path):
    """
    Opens a pickle file and returns its contents or None if file not found.

    :param path: path to the pickle file
    :return: content of the pickle file or None if error
    """
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
    except FileNotFoundError as e:
        print(e)
        return None
    return data


# TODO: add in Utility
def dump_pickle(data, path):
    """
    Dumps a pickle file on disk and returns 0 if everything went right or None
    if file not found.

    :param path: path to the pickle file where data will be written
    :param data: data to be saved on disk
    :return: 0 if success or None if error
    """
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except FileNotFoundError as e:
        print(e)
        return None
    return 0


def is_valid_location(location):
    """
    Returns True if `location` refers to a location or False otherwise.
    A valid location is one that doesn't refer to `None` or "No office location"
    which are the two options in Stackoverflow job posts for cases where there is
    no location given for a job post.

    TODO: Does No office location only refers to the case where the job post is
    for a remote job?

    :param location: string of the location to check
    :return bool: True if it is a valid location or False otherwise
    """
    if location in [None, "No office location"]:
        return False
    else:
        return True


def get_last_part_loc(location):
    # Get country or US state from `location`
    # NOTE: in most cases, location is of the form 'Berlin, Germany'
    # where country is given at the end after the comma
    if location is None:
        return None
    else:
        return location.split(",")[-1].strip()


if __name__ == '__main__':
    config = {"db_filename": DB_FILENAME,
              "analyze_tags": False,
              "analyze_locations": False,
              "analyze_salary": False,
              "analyze_industries": True}
    ipdb.set_trace()
    data_analyzer = DataAnalyzer(config)
    data_analyzer.run_analysis()
    ipdb.set_trace()