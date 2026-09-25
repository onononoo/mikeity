-- named reports. each one starts with a "-- name:" line. the "--" lines right
-- under it describe the report. the results appear on the statistics page.

-- name: busiest-centuries
-- the centuries with the most events on the timeline (deep time left out).
select century_label(century) as century, count(*) as events
from events
where century is not null
group by century
order by events desc, century
limit 12;

-- name: events-per-part
-- how the timeline is spread across the eleven parts.
select er.number as part, er.title as title, count(e.id) as events,
       round(100.0 * count(e.id) / (select count(*) from events), 1) as percent
from eras er
left join events e on e.era = er.slug
group by er.slug
order by er.number;

-- name: regions-by-part
-- which region has the most events in each part.
with counts as (
    select e.era, e.region, count(*) as n,
           row_number() over (partition by e.era order by count(*) desc, e.region) as rank
    from events e
    group by e.era, e.region
)
select er.number as part, er.title as title, r.name as top_region, c.n as events
from counts c
join eras er on er.slug = c.era
join regions r on r.slug = c.region
where c.rank = 1
order by er.number;

-- name: longest-lives
-- the people on this site who lived the longest (where both dates are known).
select name, dates, cast(died - born as integer) as years
from people
where life_known = 1
order by years desc, name
limit 10;

-- name: most-used-terms
-- glossary terms that show up in the most parts.
select t.term as term, count(u.era) as parts
from terms t
join term_usage u on u.term = t.slug
group by t.slug
having count(u.era) > 1
order by parts desc, t.term
limit 15;

-- name: common-tags
-- the most common tags on timeline events.
select tag, count(*) as events
from event_tags
group by tag
order by events desc, tag
limit 15;

-- name: longest-events
-- events on the timeline that lasted the longest (wars, empires, movements).
select date_text as dates, text as event, cast(end_year - start_year as integer) as years
from events
where deep = 0 and end_year > start_year
order by years desc
limit 10;
