import json
import os
import re
import sqlite3
import sys
import time

from bs4 import BeautifulSoup
from forex_python.converter import get_rate, get_symbol, RatesNotAvailableError
import ipdb
import requests

# TODO: module path insertion is hardcoded
sys.path.insert(0, os.path.expanduser("~/PycharmProjects/github_projects"))
from utility import genutil as g_util


DB_FILEPATH = os.path.expanduser("~/databases/dev_jobs_insights.sqlite")
# NOTE: if `CACHED_WEBPAGES_DIRPATH` is None, then the webpages will not be cached
# The webpages will then be retrieved from the internet.
CACHED_WEBPAGES_DIRPATH = os.path.expanduser("~/data/dev_jobs_insights/cache/webpages/stackoverflow_job_posts/")
SCRAPED_JOB_DATA_FILEPATH = os.path.expanduser("~/data/dev_jobs_insights/scraped_job_data.json")
CURRENCY_FILEPATH = os.path.expanduser("~/data/dev_jobs_insights/currencies.json")
DELAY_BETWEEN_REQUESTS = 2
HTTP_GET_TIMEOUT = 5
# TODO: debug code
DEBUG = False
DEST_CURRENCY = "USD"
DEST_SYMBOL = "$"


class JobsScraper:
    def __init__(self, autocommit=False):
        self.autocommit = autocommit
        # Create db connection
        self.conn = None
        # Establish a session to be used for the GET requests
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit 537.36 (KHTML, like Gecko) Chrome",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}
        self.scraped_job_posts = {}
        self.last_request_time = -sys.float_info.max
        self.job_data_keys = ['title', 'url', 'job_post_notice', 'job_post_description', 'employment_type', 'remote',
                              'relocation', 'visa', 'cached_webpage_path', 'date_posted', 'valid_through',
                              'webpage_accessed', 'company_name', 'company_description', 'company_url', 'company_size',
                              'experience_level', 'industry', 'skills', 'job_benefits', 'equity', 'min_salary',
                              'max_salary', 'currency', 'min_salary_'+DEST_CURRENCY, 'max_salary_'+DEST_CURRENCY,
                              'currency_conversion_time', 'job_location']
        # Current `job_id` being processed
        self.job_id = None
        # `currency_data` is a list of dicts. Each item in `currency_data` is a
        # dict with the keys ['cc', 'symbol', 'name'] where 'cc' is short for currency code
        self.currency_data = g_util.load_json(CURRENCY_FILEPATH)
        # Cache the rates that were already used for converting one currency to another
        # Hence, we won't have to send HTTP requests to get these rates if they
        # are already cached
        # `cached_rates` has for keys the name of the rates and the values are
        # the associated rates.
        # The name of the rate is built like this: {base_cur}_{dest_cur}
        # e.g. {'EUR_USD': 1.1391, 'EUR_CAD': 1.4976}
        self.cached_rates = {}

    def start_scraping(self):
        self.conn = g_util.connect_db(DB_FILEPATH)
        with self.conn:
            # Get all the entries' URLs
            try:
                rows = self.select_entries()
            except sqlite3.OperationalError as e:
                # g_util.print_exception("sqlite3.OperationalError")
                print("[ERROR] sqlite3.OperationalError: {}".format(e))
                self.print_log("ERROR", "sqlite3.OperationalError: {}".format(e))
                self.print_log("WARNING", "Web scraping will end!")
                return
            else:
                if not rows:
                    self.print_log("ERROR",
                                   "The returned SQL result set is empty. Web craping will end!")
                    return

        # For each entry's URL, scrape more job data from the job post's webpage
        count = 1
        at_least_one_succeeded = False
        n_skipped = 0
        self.print_log("INFO", "Total URLs to process = {}".format(len(rows)))
        for job_id, author, url in rows:
            self.job_id = job_id

            if job_id != 198845:
                continue

            try:
                self.print_log("INFO", "#{} Processing {}".format(count, url))
                count += 1

                # Initialize the dict that will store scraped data from the given job post
                # and update the job post's URL
                self.init_dict({'url': url})

                # Load cached webpage or retrieve it online
                html = self.load_cached_webpage()
                if not html:
                    self.print_log("WARNING", "The current URL {} will be skipped.".format(url))
                    continue

                bsObj = BeautifulSoup(html, 'lxml')

                # Before extracting any job data from the job post, check if the job is
                # accepting applications by extracting the message
                # "This job is no longer accepting applications."
                # This notice is located in
                # body > div.container > div#content > aside.s-notice
                # NOTE: Usually when this notice is present in a job post, the json job
                # data is not found anymore within the html of the job post
                self.process_notice(bsObj)

                # Get linked data from <script type="application/ld+json">
                self.process_linked_data(bsObj)

                # Get job data (e.g. salary, remote, location) from the <header>
                self.process_header(bsObj)

                # Get job data from the Overview section
                self.process_overview_items(bsObj)

                at_least_one_succeeded = True
                self.print_log("INFO", "Finished Processing {}".format(url))
            except KeyError as e:
                # g_util.print_exception("[job_id={}] KeyError")
                self.print_log("ERROR", "KeyError: {}".format(e))
                self.print_log("WARNING", "The current URL {} will be skipped".format(url))
                n_skipped += 1
                continue
        print()
        # Save scraped data into json file
        # ref.: https://stackoverflow.com/a/31343739 (presence of unicode strings,
        # e.g. EURO currency symbol)
        if at_least_one_succeeded and g_util.dump_json_with_codecs(SCRAPED_JOB_DATA_FILEPATH, self.scraped_job_posts) == 0:
            self.print_log("INFO", "Scraped data saved in {}".format(SCRAPED_JOB_DATA_FILEPATH))
        else:
            self.print_log("ERROR", "Scraped data couldn't be saved")
            self.print_log("INFO", "Skipped URLs={}/{}".format(n_skipped, len(rows)))

    def init_dict(self, updated_values):
        self.scraped_job_posts[self.job_id] = {}.fromkeys(self.job_data_keys)
        # Add updated values
        self.update_dict(updated_values)

    def get_dict_value(self, key):
        return self.scraped_job_posts[self.job_id][key]

    def update_dict(self, updated_values):
        for key, new_value in updated_values.items():
            self.print_log("DEBUG", "Trying to update the [key, value]=['{}', '{}']".format(key, new_value))
            current_value = self.scraped_job_posts[self.job_id].get(key)
            if current_value:
                self.print_log("DEBUG",
                               "The key='{}' already has a value='{}'. Thus the new_value='{}' will be ignored.".format(
                                   key, current_value, new_value
                               ))
                if current_value != new_value:
                    self.print_log("CRITICAL", "The new_value='{}' is not equal to current_value='{}'".format(
                        new_value, current_value
                    ))
                return 1
            else:
                self.scraped_job_posts[self.job_id].update({key: new_value})
                self.print_log("DEBUG", "The key='{}' was updated with value='{}'".format(key, new_value))
        return 0

    @staticmethod
    # Get the location data in a linked data JSON object
    def get_loc_in_ld(linked_data):
        job_locations = linked_data.get('jobLocation')
        if job_locations:
            processed_locations = []
            for location in job_locations:
                processed_locations.append({'city': location['address']['addressLocality'],
                                            'country': location['address']['addressCountry']})
            return processed_locations
        else:
            return None

    @staticmethod
    def get_min_max_salary(salary_range):
        min_salary, max_salary = salary_range.replace(" ", "").split("-")
        min_salary = int(min_salary)
        max_salary = int(max_salary)
        return min_salary, max_salary

    def get_webpage(self, url):
        html = None
        current_delay = time.time() - self.last_request_time
        diff_between_delays = current_delay - DELAY_BETWEEN_REQUESTS
        if diff_between_delays < 0:
            self.print_log("INFO",
                           "Waiting {} seconds before sending next HTTP request...".format(abs(diff_between_delays)))
            time.sleep(abs(diff_between_delays))
            self.print_log("INFO", "Time is up! HTTP request will be sent.")
        try:
            req = self.session.get(url, headers=self.headers, timeout=HTTP_GET_TIMEOUT)
            html = req.text
        except OSError as e:
            # g_util.print_exception("OSError")
            self.print_log("ERROR", "OSError: {}".format(e))
            return None
        else:
            if req.status_code == 404:
                self.print_log("ERROR", "PAGE NOT FOUND. The URL {} returned a 404 status code.".format(url))
                return None
        self.last_request_time = time.time()
        self.print_log("INFO", "The webpage is retrieved from {}".format(url))
        return html

    # Load the cached webpage HTML if the webpage is found locally. If it isn't found
    # locally, then we will try to retrieve it with a GET request
    def load_cached_webpage(self):
        html = None
        url = self.get_dict_value('url')
        # Path where the cached webpage's HTML will be saved
        filepath = os.path.join(CACHED_WEBPAGES_DIRPATH, "{}.html".format(self.job_id))

        if CACHED_WEBPAGES_DIRPATH:
            html = g_util.read_file(filepath)
        else:
            self.print_log("WARNING", "The caching option is disabled")
        if html:
            self.print_log("INFO", "The cached webpage HTML is loaded from {}".format(filepath))
            # Update cached webpage path and its datetime modified
            self.update_dict({'cached_webpage_path': filepath,
                              'webpage_accessed': os.path.getmtime(filepath)})
        else:
            self.print_log("INFO",
                           "Instead the webpage HTML @ {} will be retrieved with a GET request".format(url))
            # Get the webpage HTML
            html = self.get_webpage(url)
            if html:
                # Update the datetime the webpage was retrieved (though not 100% accurate)
                self.update_dict({'webpage_accessed': time.time()})
                if self.save_webpage_locally(url, filepath, html) == 0:
                    # Update the path the webpage is cached
                    self.update_dict({'cached_webpage_path': filepath})
            else:
                # No html retrieved at all
                return None

        return html

    def process_header(self, bsObj):
        # Get more job data (e.g. salary, remote, location) from the <header>
        # The job data in the <header> are found in this order:
        # 1. Title of job post
        # 2. company name
        # 3. office location
        # 4. Other job data: Salary, Remote, Visa sponsor, Paid relocation, ...
        # NOTE: the company name and office location are found on the same line
        # separated by a vertical line. The other job data are to be all found on
        # the same line (after the company name and office location) and these
        # job data are all part of a class that starts with '-', e.g. '-salary',
        # '-remote' or '-visa'
        url = self.get_dict_value('url')

        # 1. Get title of job post
        pattern = "header.job-details--header > div.grid--cell > h1.fs-headline1 > a"
        self.process_text_in_tag(bsObj, pattern, 'title')

        # 2. Get company name
        pattern = "header.job-details--header > div.grid--cell > div.fc-black-700 > a"
        self.process_text_in_tag(bsObj, pattern, 'company_name')

        # 3. Get the office location which is located on the same line as the company name
        pattern = "header.job-details--header > div.grid--cell > div.fc-black-700 > span.fc-black-500"
        self.process_text_in_tag(bsObj, pattern, 'job_location', self.process_location_text)

        ipdb.set_trace()

        # 4. Get the other job data on the next line after the company name and location
        # TODO: simplify the scraping of these other job data
        pattern = "header.job-details--header > div.grid--cell > div.mt12"
        div_tag = bsObj.select_one(pattern)
        if div_tag:
            # Each `div_tag`'s child is associated to a job item (e.g. salary, remote)
            # and is a <span> tag with a class that starts with '-'
            # Example: header.job-details--header > div.grid--cell > .mt12 > span.-salary.pr16
            children = div_tag.findChildren()
            for child in children:
                # Each job data text is found within <span> with a class that starts
                # with '-', e.g. <span class='-salary pr16'>
                # NOTE: we need the child element's class that starts with '-' because
                # we will then know how to name the extracted job data item
                child_class = [tag_class for tag_class in child.attrs['class'] if tag_class.startswith('-')]
                if child_class: # class that starts with '-'
                    # Get the <div>'s class name without the '-' at the beginning,
                    # this will correspond to the type of job data (e.g. salary, remote, relocation, visa)
                    key_name = child_class[0][1:]
                    ipdb.set_trace()
                    value = child.text
                    if value:  # value = text
                        self.print_log("INFO", "The {} is found. URL @ {}".format(key_name, url))
                        # Get the text (e.g. $71k - 85k) by removing any \r and \n around the string
                        value = value.strip()
                        if key_name == 'salary':
                            updated_values = self.process_salary_text(value)
                            if updated_values:
                                self.update_dict(updated_values)
                            else:
                                pass
                        else:
                            self.update_dict({key_name: value})
                    else:
                        self.print_log("ERROR", "No text found for the job data key {}. URL @ {}".format(
                            key_name, url))
                else:
                    self.print_log("ERROR", "The <span>'s class doesn't start with '-'. URL @ {}".format(url))
        else:
            msg = "Couldn't extract the other job data @ URL {}. The other " \
                  "job data should be found in {}".format(url, pattern)
            self.print_log("WARNING", msg)

    def process_linked_data(self, bsObj):
        # Get linked data from <script type="application/ld+json">:
        # On the webpage of a job post, important data about the job post
        # (e.g. job location or salary) can be found in <script type="application/ld+json">
        # This linked data is a JSON object that stores important job info like
        # employmentType, experienceRequirements, jobLocation
        script_tag = bsObj.find(attrs={'type': 'application/ld+json'})
        url = self.get_dict_value('url')
        if script_tag:
            """
            The linked data found in <script type="application/ld+json"> is a json
            object with the following keys:
            '@context', '@type', 'title', 'skills', 'description', 'datePosted',
            'validThrough', 'employmentType', 'experienceRequirements',
            'industry', 'jobBenefits', 'hiringOrganization', 'baseSalary', 'jobLocation'
            """
            linked_data = json.loads(script_tag.get_text())
            updated_values = {'title': linked_data.get('title'),
                              'job_post_description': linked_data.get('description'),
                              'employment_type': linked_data.get('employmentType'),
                              'date_posted': linked_data.get('datePosted'),
                              'valid_through': linked_data.get('validThrough'),
                              'experience_level': self.str_to_list(linked_data.get('experienceRequirements')),
                              'industry': linked_data.get('industry'),
                              'skills': linked_data.get('skills'),
                              'job_benefits': linked_data.get('jobBenefits'),
                              'company_description': linked_data.get('hiringOrganization').get('description'),
                              'company_name': linked_data.get('hiringOrganization').get('name'),
                              'company_site_url': linked_data.get('hiringOrganization').get('sameAs'),
                              'min_salary': linked_data.get('baseSalary').get('value').get('minValue'),
                              'max_salary': linked_data.get('baseSalary').get('value').get('maxValue'),
                              'currency': linked_data.get('baseSalary').get('currency'),
                              'job_location': self.get_loc_in_ld(linked_data)
                              }
            self.update_dict(updated_values)
            self.print_log("INFO", " The linked data from URL {} were successfully scraped".format(url))
        else:
            # Reasons for not finding <script type='application/ld+json'>:
            # maybe the page is not found anymore (e.g. job post removed) or
            # the company is not longer accepting applications
            msg = "The page @ URL {} doesn't contain any SCRIPT tag with type='application/ld+json'".format(url)
            self.print_log("WARNING", msg)

    def process_notice(self, bsObj):
        pattern = "body > div.container > div#content > aside.s-notice"
        self.process_text_in_tag(bsObj, pattern, 'job_post_notice')

    def process_overview_items(self, bsObj):
        # Get job data from the Overview section. There are two places within
        # Overview section that will be extracted for more job data:
        # 1. in the "About this job" sub-section of Overview
        # 2. in the "Technologies" sub-section of Overview
        # NOTE: both sub-sections are located within <div id=""overview-items>
        # [overview-items]
        url = self.get_dict_value('url')
        convert_keys = {'job_type': 'employment_type',
                        'technologies': 'skills'}

        # 1. Get more job data (e.g. role, industry, company size) in the
        # "About this job" section. Each item is located in
        # "#overview-items > .mb32 > .job-details--about > .grid--cell6 > .mb8"
        # NOTE: these job data are presented in two columns, with three items per column
        pattern = "#overview-items > .mb32 > .job-details--about > .grid--cell6 > .mb8"
        div_tags = bsObj.select(pattern)
        if div_tags:
            # Each `div_tag` corresponds to a job data item
            # e.g. Job type: Full-time, Company type: Private
            for div_tag in div_tags:
                # Sample raw text: '\nJob type: \nContract\n'
                temp = div_tag.text.strip().split(":")
                job_data_key, job_data_value = temp[0].strip(), temp[1].strip()
                # The field names should all be lowercase and spaces be replaced
                # with underscores e.g. Job type ---> job_type
                job_data_key = job_data_key.replace(" ", "_").lower()
                # Convert the key name to use the standard key name
                job_data_key = convert_keys.get(job_data_key, job_data_key)
                self.update_dict({job_data_key: job_data_value})
        else:
            msg = "Couldn't extract job data from the 'About this job' section @ the URL {}. " \
                  "The job data should be found in {}".format(url, pattern)
            self.print_log("ERROR", msg)

        # [overview-items]
        # 2. Get the list of technologies, e.g. ruby, python, html5
        # NOTE: unlike the other job data in "overview_items", the technologies
        # are given as a list
        pattern = "#overview-items > .mb32 > div > a.job-link"
        link_tags = bsObj.select(pattern)
        if link_tags:
            for link_tag in link_tags:
                technology = link_tag.text
                if technology:
                    pass
                    #entries_data[job_id]["overview_items"]["technologies"].append(technology)
                else:
                    msg = "No text found for the technology with href={}. URL @ {}".format(link_tag["href"], url)
                    self.print_log("ERROR", msg)
        else:
            msg = "Couldn't extract technologies from the 'Technologies' section @ the URL {}. " \
                  "The technologies should be found in {}".format(url, pattern)
            self.print_log("ERROR", msg)

    def process_text_in_tag(self, bsObj, pattern, key_name, process_text_method=None):
        url = self.get_dict_value('url')
        tag = bsObj.select_one(pattern)
        if tag:
            value = tag.text
            if value:
                self.print_log("INFO", "The {} is found. URL @ {}".format(key_name, url))
                if process_text_method:
                    value = process_text_method(value)
                self.update_dict({key_name: value})
            else:
                self.print_log("WARNING", "The {} is empty. URL @ {}".format(key_name, url))
        else:
            msg = "Couldn't extract the {} @ the URL {}. The {} should be found in {}".format(
                key_name, url, key_name, pattern)
            self.print_log("WARNING", msg)

    def process_location_text(self, text):
        # The text where you find the location looks like this:
        # '\n|\r\nNo office location                    '
        # strip() removes the first '\n' and the right spaces. Then split('\n')[-1]
        # extracts the location string
        text = text.strip().split('|')[-1].strip()
        if ',' in text:
            text = dict(zip(['city', 'country'], text.split(',')))
        else:
            self.print_log("DEBUG", "No country or city found in job location: {}".format(text))
        return [text]

    def process_salary_text(self, salary_text):
        ipdb.set_trace()
        updated_values = {}
        # Check if the salary text contains 'Equity', e.g. '€42k - 75k | Equity'
        if 'Equity' in salary_text:
            self.print_log("DEBUG", "Equity found in the salary text {}".format(salary_text))
            # Split the salary text to get the `salary_range` and `equity`
            # e.g. '€42k - 75k | Equity' will be splitted as '€42k - 75k' and 'Equity'
            salary_range, equity = [v.strip() for v in salary_text.split('|')]
            updated_values['equity'] = equity
        else:
            self.print_log("DEBUG", "Equity is not found in the salary text {}".format(salary_text))
            salary_range = salary_text
        updated_values = self.process_salary_range(salary_range)
        if updated_values:
            self.print_log("DEBUG", "salary text {} was successfully processed!")
            return updated_values
        else:
            return None

    def process_salary_range(self, salary_range):
        # Dict that will be returned if everything goes right. If not, then
        # `None` will be returned
        updated_values = {'min_salary': None,
                          'max_salary': None,
                          'currency': None,
                          'min_salary_' + DEST_CURRENCY: None,
                          'max_salary_' + DEST_CURRENCY: None,
                          'currency_conversion_time': None
                          }
        ipdb.set_trace()
        # Extract the currency symbol at the beginning of the salary range text
        # e.g. '€' will be extracted from €42k - 75k'
        # `results` is either:
        #       - a tuple (currency_symbol, end) or
        #       - None (if no currency symbol could be extracted)
        #
        # NOTE: `end` refers to the position of the first number in the
        # `salary_range` text, e.g. end=1 if salary_range='€42k - 75k'
        results = self.get_currency_symbol(salary_range)
        if results:
            # `results` is a tuple
            currency_symbol, end = results
            # Get the currency code based on the currency symbol
            currency_code = self.get_currency_code(currency_symbol)
            updated_values['currency'] = currency_code
            # Get the salary range only without the currency symbol at the beginning
            # e.g. '€42k - 75k' --> '42k - 75k'
            salary_range = salary_range[end:]
            # Replace the letter 'k' with '000', e.g. 42k --> 42000
            salary_range = salary_range.replace('k', '000')
            # Get the minimum and maximum salary separately
            # e.g. '42000 - 75000' --> min_salary=42000, max_salary=75000
            min_salary, max_salary = self.get_min_max_salary(salary_range)
            updated_values['min_salary'] = min_salary
            updated_values['max_salary'] = max_salary
            # Convert the salary to DEST_CURRENCY (default is USD)
            if currency_code != DEST_CURRENCY:
                try:
                    updated_values['currency'+DEST_CURRENCY] = DEST_CURRENCY
                    ipdb.set_trace()
                    min_salary_converted, timestamp = self.convert_currency(min_salary, currency_code, DEST_CURRENCY)
                    updated_values['min_salary' + DEST_CURRENCY] = min_salary_converted
                    updated_values['currency_conversion_time'] = timestamp
                    max_salary_converted, _ = self.convert_currency(max_salary, currency_code, DEST_CURRENCY)
                    updated_values['max_salary' + DEST_CURRENCY] = max_salary_converted
                    return updated_values
                except TypeError:
                    # g_util.print_exception("TypeError")
                    self.print_log("ERROR", "TypeError: {}".format(e))
                    return None
            else:
                msg = "The salary {} will not be converted to {} because it is already in the desired currency".format(
                    salary_range, DEST_CURRENCY)
                self.print_log("DEBUG", msg)
                return updated_values
        else:
            self.print_log("WARNING",
                           "No currency symbol could be retrieved from the salary text {}".format(salary_range))
            return None

    # Get currency symbol located at the BEGINNING of the string, e.g. '€42k - 75k'
    def get_currency_symbol(self, text):
        # returned value is either:
        #   - a tuple (currency_symbol, end) or
        #   - None
        # NOTE: `end` refers to the position of the first number in the salary `text`
        regex = r"^(\D+)"
        match = re.search(regex, text)
        if match:
            self.print_log("DEBUG", "Found currency {} in text {}".format(match.group(), text))
            return match.group(), match.end()
        else:
            self.print_log("ERROR", "No currency found in text {}".format(text))
            return None

    def get_currency_code(self, currency_symbol):
        # NOTE: there is no 1-to-1 mapping when going from currency symbol
        # to currency code
        # e.g. the currency symbol £ is used for the currency codes EGP, FKP, GDP,
        # GIP, LBP, and SHP
        # Search into the `currency_data` list for all the currencies that have
        # the given `currency_symbol`. Each item in `currency_data` is a dict
        # with the keys ['cc', 'symbol', 'name'].
        results = [item for item in self.currency_data if item["symbol"] == currency_symbol]
        # NOTE: C$ is used as a currency symbol for Canadian Dollar instead of $
        # However, C$ is already the official currency symbol for Nicaragua Cordoba (NIO)
        # Thus we will assume that C$ is related to the Canadian Dollar.
        if currency_symbol != "C$" and len(results) == 1:
            print("[DEBUG] [{}] Found only one currency code {} associated with "
                  "the given currency symbol {}".format(self.job_id, results[0]["cc"], currency_symbol))
            return results[0]["cc"]
        else:
            # Two possible cases
            # 1. Too many currency codes associated with the given currency symbol
            # 2. It is not a valid currency symbol
            if currency_symbol == "A$":  # Australian dollar
                currency_code = "AUD"
            elif currency_symbol == "C$":  # Canadian dollar
                currency_code = "CAD"
            elif currency_symbol == "£":  # We assume £ is always associated with the British pound
                currency_code = "GBP"  # However, it could have been EGP, FKP, GIP, ...
            else:
                print("[ERROR] [{}] Could not get a currency code from {}".format(self.job_id, currency_symbol))
                return None
            return currency_code

    def convert_currency(self, amount, base_cur_code, dest_cur_code='USD'):
        ipdb.set_trace()
        converted_amount = None
        try:
            # Get the rate from cache
            rate_used = self.cached_rates.get['{}_{}'.format(base_cur_code, dest_cur_code)]
            if rate_used:
                self.print_log("DEBUG",
                               "The cached rate {} is used for {}-->{}".format(
                                   rate_used, base_cur_code, dest_cur_code))
            else:
                self.print_log("DEBUG",
                               "No cache rate found for {}-->{}".format(base_cur_code, dest_cur_code))
                # Get the rate and cache it
                self.print_log("DEBUG", "The rate {} is cached for {}-->{}".format(rate_used, base_cur_code, dest_cur_code))
                rate_used = get_rate(base_cur_code, dest_cur_code)
                self.cached_rates['{}_{}'.format(base_cur_code, dest_cur_code)] = rate_used
            # Convert the base currency to the desired currency with the retrieved rate
            converted_amount = rate_used * amount
        except RatesNotAvailableError:
            # g_util.print_exception("RatesNotAvailableError")
            self.print_log("ERROR", "RatesNotAvailableError: {}".format(e))
            self.print_log("ERROR",
                           "The amount {} in {} couldn't be converted to {}".format(
                               amount, base_cur_code, dest_cur_code))
            return None
        except requests.exceptions.ConnectionError:
            self.print_log("ERROR", "requests.exceptions.ConnectionError: {}".format(e))
            self.print_log("ERROR", "No connection to api.fixer.io (e.g. working offline)")
            return None
        else:
            converted_amount = int(round(converted_amount))
            # NOTE: round(a, 2) doesn't work in python 2.7:
            # >> a = 0.3333333
            # >> round(a, 2),
            # Use the following in python2.7:
            # >> float(format(a, '.2f'))
            return converted_amount, time.time()

    def print_log(self, level, msg, length_msg=300):
        if len(msg) > length_msg:
            msg = msg[:length_msg] + " [...]"
        if level != "DEBUG":
            print("[{}] [{}] {}".format(level, self.job_id, msg))

    def save_webpage_locally(self, url, filepath, html):
        if CACHED_WEBPAGES_DIRPATH:
            if g_util.write_file(filepath, html) == 0:
                self.print_log("INFO", "The webpage is saved in {}. URL is {}".format(filepath, url))
                return 0
            else:
                self.print_log("WARNING", "The webpage @ URL {} will not be saved locally".format(url))
                return 1
        else:
            msg = "The caching option is disabled. Thus, the webpage @ URL {} " \
                  "will not be saved locally.".format(url)
            self.print_log("WARNING", msg)
            return 1

    @staticmethod
    def str_to_list(str_v):
        # If string of comma-separated values (e.g. 'Architecture, Developer APIs, Healthcare'),
        # return a list of values instead, e.g. ['Architecture', 'Developer APIs', 'Healthcare']
        return [v.strip() for v in str_v.split(',')]

    def select_entries(self):
        """
        Returns all job_id, author and url from the `entries` table

        :return:
        """
        sql = '''SELECT job_id, author, url FROM entries'''
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchall()


def main():
    if g_util.create_directory_prompt(CACHED_WEBPAGES_DIRPATH):
        print("[WARNING] The program will exit")
        sys.exit(1)

    # Start the scraping of job posts
    JobsScraper().start_scraping()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        # g_util.print_exception("KeyboardInterrupt")
        # print("[ERROR] KeyboardInterrupt: {}".format(e))
        pass
