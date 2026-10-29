with dates as (
    select d::date as full_date
    from generate_series('2025-01-01'::date, '2027-12-31'::date, interval '1 day') as d
)

select
    to_char(full_date, 'YYYYMMDD')::int          as date_key,
    full_date,
    extract(year from full_date)::int            as year,
    extract(quarter from full_date)::int         as quarter,
    extract(month from full_date)::int           as month,
    to_char(full_date, 'FMMonth')                as month_name,
    extract(day from full_date)::int             as day,
    extract(isodow from full_date)::int          as day_of_week,
    to_char(full_date, 'FMDay')                  as day_name,
    extract(isodow from full_date) in (6, 7)     as is_weekend
from dates