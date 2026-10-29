-- Har customer ki sirf ek hi current row honi chahiye.
-- Ye query galat rows return karti hai. Khali aaye to test pass.
select
    customer_id,
    count(*) as current_rows
from {{ ref('dim_customer') }}
where is_current
group by customer_id
having count(*) <> 1