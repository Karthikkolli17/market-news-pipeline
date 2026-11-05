with source as (

    select * from {{ source('raw', 'raw_news') }}
),

select
    cast(article_id as varchar) || '-' || ticker    as article_ticker_id,
    article_id,
    upper(trim(ticker))                             as ticker
from source