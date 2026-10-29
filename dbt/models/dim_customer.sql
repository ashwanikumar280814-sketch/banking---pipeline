with versions as (
    select
        customer_id,
        full_name_masked,
        email_masked,
        email_token,
        phone_masked,
        address_hash,
        kyc_status,
        created_at,
        event_ts,
        kafka_offset
    from {{ source('silver', 'customers_history') }}
    where op <> 'd'
)

select
    md5(customer_id::text || '|' || kafka_offset::text)  as customer_key,
    customer_id,
    full_name_masked,
    email_masked,
    email_token,
    phone_masked,
    address_hash,
    kyc_status,
    created_at,
    event_ts                                              as valid_from,
    lead(event_ts) over (
        partition by customer_id
        order by event_ts, kafka_offset
    )                                                     as valid_to,
    lead(event_ts) over (
        partition by customer_id
        order by event_ts, kafka_offset
    ) is null                                             as is_current
from versions