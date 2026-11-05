with source as (

    select * from {{ source('raw', 'raw_news') }}
),

deduped as (

    select *
    from source
    qualify row_number() over (
        partition by article_id
        order by published_epoch desc, ticker
    ) = 1
)

select
    article_id,
    to_timestamp(published_epoch) at time zone 'UTC'                    as published_at_utc,
    cast(to_timestamp(published_epoch) at time zone 'UTC' as date)      as published_date_utc,
    trim(headline)                                                      as headline,
    nullif(trim(summary), '')                                           as summary,
    trim(source)                                                        as source,
    url,
    loaded_at
from deduped