with txn as (
    select * from {{ source('silver', 'transactions') }}
),

current_customer as (
    select customer_id, customer_key
    from {{ ref('dim_customer') }}
    where is_current
)

select
    t.transaction_id,
    t.account_id,
    a.customer_id,
    cc.customer_key,
    t.merchant_id,
    to_char(t.created_at, 'YYYYMMDD')::int  as date_key,
    t.txn_type,
    t.amount,
    t.currency,
    t.status,
    t.channel,
    t.device_id,
    t.is_late,
    t.created_at,
    t.source_event_ts
from txn t
left join {{ ref('dim_account') }}  a  on a.account_id  = t.account_id
left join {{ ref('dim_merchant') }} m  on m.merchant_id = t.merchant_id
left join current_customer cc          on cc.customer_id = a.customer_id