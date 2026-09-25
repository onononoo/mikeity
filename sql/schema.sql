-- schema for the history database.
-- years are numbers: negative means before the common era (bce).
-- "deep" events (like the big bang) use huge negative years and have no century.

pragma foreign_keys = on;

create table regions (
    slug        text primary key,
    name        text not null,
    description text not null default ''
);

create table eras (
    slug        text primary key,
    number      integer not null unique,
    title       text not null,
    starts      text not null,          -- as written, e.g. 'c. 3500 bce'
    ends        text not null,
    start_year  real not null,
    end_year    real not null,
    summary     text not null,
    words       integer not null default 0,
    check (start_year <= end_year)
);

create table events (
    id          integer primary key,
    date_text   text not null,
    start_year  real not null,
    end_year    real not null,
    approx      integer not null default 0 check (approx in (0, 1)),
    deep        integer not null default 0 check (deep in (0, 1)),
    century     integer,                -- 15 = 15th century, -5 = 5th century bce
    text        text not null,
    era         text not null references eras (slug),
    region      text not null references regions (slug),
    check (start_year <= end_year)
);

create index events_by_year on events (start_year);
create index events_by_era on events (era);
create index events_by_region on events (region);

create table event_tags (
    event_id    integer not null references events (id),
    tag         text not null,
    primary key (event_id, tag)
);

create table people (
    slug        text primary key,
    name        text not null,
    dates       text not null,
    born        real,
    died        real,
    life_known  integer not null default 0 check (life_known in (0, 1)),  -- 1 if birth and death years are both given
    role        text not null,
    about       text not null,
    era         text not null references eras (slug),
    region      text not null references regions (slug)
);

create table terms (
    slug        text primary key,
    term        text not null unique,
    definition  text not null
);

create table term_usage (
    term        text not null references terms (slug),
    era         text not null references eras (slug),
    primary key (term, era)
);

-- a handy view: every event with its era and region names filled in
create view timeline as
select
    e.id,
    e.date_text,
    e.start_year,
    e.end_year,
    e.text,
    er.number as part,
    er.title  as era_title,
    r.name    as region_name
from events e
join eras er on er.slug = e.era
join regions r on r.slug = e.region
order by e.start_year, e.end_year;
