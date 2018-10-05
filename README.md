# Data analysis of developer job posts from Stack Overflow [WORK-IN-PROGRESS]

<!-- TOC depthFrom:2 depthTo:6 withLinks:1 updateOnSave:1 orderedList:0 -->

- [Introduction](#introduction)
- [Sources of data](#sources-of-data)
- [Map of the distribution of job posts around the world](#map-of-the-distribution-of-job-posts-around-the-world)
- [Map of the distribution of job posts in the USA](#map-of-the-distribution-of-job-posts-in-the-usa)
- [Top 20 most popular industries and technologies](#top-20-most-popular-industries-and-technologies)
- [Histogram: Mid-range salaries among Stack Overflow developer job posts](#histogram-mid-range-salaries-among-stack-overflow-developer-job-posts)
- [TODOs](#todos)

<!-- /TOC -->

## Introduction
**dev-jobs-insights** is a data mining project written in **Python3** with the
main objective of **extracting meaningful insights** from developer job posts.
These insights can help us in getting a more accurate picture of what the
developer job market looks like so we can make better decisions (e.g. what
technologies to focus on to increase our chance of finding a job).

I will show some of the important graphs and maps that are generated so you can
have an idea what the project is all about.

More detailed information can be found from the project's website @
https://raul23.github.io/projects/dev-jobs-insights.html. There you will find
more graphs (interactive scatter plots) and explanations about how the various
scripts work for ultimately generating the graphs and maps.

## Sources of data
The job data comes from **Stack Overflow**'s developer jobs
[website](https://stackoverflow.com/jobs) and
[RSS feed](https://stackoverflow.com/jobs/feed). Eventually, other sources of
job data from other sites will also be integrated.

Here is a summary of the job data:  
<table>
    <tr>
        <td align="center"><b>Sources of data</b></td>
        <td align="center">Stack Overflow's <a href="https://stackoverflow.com/jobs/feed">RSS feed</a> and <a href="https://stackoverflow.com/jobs">jobs website</a></td>
    </tr>
    <tr>
        <td align="center"><b>Total number of job posts</b></td>
        <td align="center">1000</td>
    </tr>
    <tr>
        <td align="center"><b>Total number of companies</b></td>
        <td align="center">561</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
</table>

**NOTE:** 1000 is a small sample for extracting solid insights about the
developer job market but eventually more job data will get integrated. For now
I am using this small set for testing the whole pipeline for generating the
graphs, maps and reports.

## Map of the distribution of job posts around the world
<p align="center"><img src="https://bit.ly/2OvqmLG"/></p>
<p align="center"></p>

The next table shows stats about the data used for generating the world map:   
<table>
    <tr>
        <td align="center"><b>Number of job posts</b></td>
        <td align="center">999</td>
    </tr>
    <tr>
        <td align="center"><b>Number of countries</b></td>
        <td align="center">41</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
    <tr>
        <td align="center"><b>Top 5 countries (based on number of job posts)</b></td>
        <td align="center">
          United States <b>(377)</b> <br/>
          Germany <b>(241)</b> <br/>
          United Kingdom <b>(84)</b> <br/>
          Netherlands <b>(43)</b> <br/>
          Switzerland <b>(34)</b></td>
    </tr>
    <tr>
        <td align="center"><b>Top 5 job locations (based on number of job posts)</b></td>
        <td align="center">
        Berlin, 10117, Deutschland <b>(58)</b> <br/>
        London, Greater London, England, SW1A 2DU, UK <b>(46)</b> <br/>
        NYC, New York, USA <b>(33)</b> <br/>
        Hamburg, 20095, Deutschland <b>(31)</b> <br/>
        SF, California, USA <b>(26)</td>
    </tr>
</table>

Each dot on the map represents a particular job location (or address) from a job
post and the size of the dot gives the relative importance of the job location
compared to other job locations. Thus, a bigger dot for a particular location
means that more job posts are associated with this location compared to other
locations having smaller dots.

Each job post can be associated with more than one job location and a job
location consists of three components: city, region (aka state or province), and
country.

## Map of the distribution of job posts in the USA
<p align="center"><img src="https://bit.ly/2OEA7Y2"/></p>
<p align="center"></p>

The next table shows stats about the data used for generating the USA map:   
<table>
    <tr>
        <td align="center"><b>Number of job posts</b></td>
        <td align="center">377</td>
    </tr>
    <tr>
        <td align="center"><b>Number of US states</b></td>
        <td align="center">31</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
    <tr>
        <td align="center"><b>Top 5 US states (based on number of job posts)</b></td>
        <td align="center">
        California <b>(73)</b> <br/>
        New York <b>(40)</b> <br/>
        Pennsylvania <b>(32)</b> <br/>
        Massachusetts <b>(25)</b> <br/>
        New Jersey <b>(23)</b></td>
    </tr>
    <tr>
        <td align="center"><b>Top 5 job locations (based on number of job posts)</b></td>
        <td align="center">
        NYC, New York, USA <b>(33)</b> <br/>
        SF, California, USA <b>(26)</b> <br/>
        Philadelphia, Philadelphia County, Pennsylvania, USA <b>(22)</b> <br>
        Jersey City, Hudson County, New Jersey, USA <b>(13)</b> <br/>
        Columbus, Franklin County, Ohio, USA <b>(12)</b></td>
    </tr>
</table>

## Top 20 most popular industries and technologies
<p align="center"><img src="https://bit.ly/2P87UG2"/></p>
<p align="center"></p>

The next table shows stats about the data used for generating the previous bar
chart **"Top 20 most popular industries"**:  
<table>
    <tr>
        <td align="center"><b>Number of job posts</b></td>
        <td align="center">----</td>
    </tr>
    <tr>
        <td align="center"><b>Total number of industries</b></td>
        <td align="center">----</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
</table>

<br/>

<p align="center"><img src="https://bit.ly/2QsCMRL"/></p>
<p align="center"><b>Go Python!</b></p>

The next table shows stats about the data used for generating the previous bar
chart **"Top 20 most popular technologies"**:  
<table>
    <tr>
        <td align="center"><b>Number of job posts</b></td>
        <td align="center">----</td>
    </tr>
    <tr>
        <td align="center"><b>Total number of technologies</b></td>
        <td align="center">----</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
</table>

## Histogram: Mid-range salaries among Stack Overflow developer job posts
<p align="center"><img src="https://bit.ly/2xYAbs2"/></p>
<p align="center"></p>

The next table shows stats about the data used for generating the previous histogram:
<table>
    <tr>
        <td align="center"><b>Number of job posts</b></td>
        <td align="center">----</td>
    </tr>
    <tr>
        <td align="center"><b>Published dates</b></td>
        <td align="center">2018-09-18 to 2018-09-28</td>
    </tr>
</table>

<br/>

The job salaries provided by the companies consist in a minimum and maximum
values, e.g. €50k - 65k. Thus, in order to have one salary number per job post,
I converted the range of salaries into a mid-range salary, e.g. €50k - 65k -->
€57.5

## TODOs
- Integrate more job data from Stack Overflow and other sites
- Fully automate the whole pipeline of generating the graphs, maps, and reports
- Display job data summary directly on each graph or map
