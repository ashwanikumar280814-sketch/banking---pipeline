with ranked as (
    select
        *,
        row_number() over (
            partition by account_id
            order by kafka_offset desc
        ) as rn
    from {{ source('silver', 'accounts_history') }}
)

select
    account_id,
    customer_id,
    account_type,
    status           as account_status,
    credit_limit,
    opened_at
from ranked
where rn = 1
  and op <> 'd'