with latest as (
    select
        payload->'payload'->'after' as rec,
        payload->'payload'->>'op'   as op,
        row_number() over (
            partition by payload->'payload'->'after'->>'merchant_id'
            order by kafka_offset desc
        ) as rn
    from {{ source('bronze', 'raw_events') }}
    where topic = 'bank.public.merchants'
      and payload->'payload'->>'op' in ('r', 'c', 'u')
)

select
    (rec->>'merchant_id')::int as merchant_id,
    rec->>'name'               as merchant_name,
    rec->>'category'           as merchant_category,
    rec->>'country'            as merchant_country
from latest
where rn = 1