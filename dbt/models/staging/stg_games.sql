{#
  Staging model: one row per game.

  Grain: game_id.

  Steps:
    1. Read the raw VARIANT rows (one per landed file).
    2. LATERAL FLATTEN the payload:data array into one row per game.
    3. Cast fields to proper types.
    4. Deduplicate: every ingestion run lands a full season, so the same
       game_id appears once per file. Keep the copy from the most recent
       extraction.
#}

with source as (

    select
        payload,
        source_file,
        loaded_at
    from {{ source('raw', 'games_raw') }}

),

flattened as (

    select
        f.value:id::int                                   as game_id,
        left(f.value:date::string, 10)::date              as game_date,
        f.value:season::int                               as season,
        f.value:status::string                            as status,
        f.value:postseason::boolean                       as is_postseason,
        f.value:home_team:id::int                         as home_team_id,
        f.value:home_team:abbreviation::string            as home_team_abbreviation,
        f.value:home_team_score::int                      as home_team_score,
        f.value:visitor_team:id::int                      as visitor_team_id,
        f.value:visitor_team:abbreviation::string         as visitor_team_abbreviation,
        f.value:visitor_team_score::int                   as visitor_team_score,
        try_to_timestamp_ntz(
            source.payload:extracted_at::string,
            'YYYYMMDD"T"HH24MISS"Z"'
        )                                                 as extracted_at,
        source.source_file,
        source.loaded_at
    from source,
        lateral flatten(input => source.payload:data) f

),

deduplicated as (

    select *
    from flattened
    qualify row_number() over (
        partition by game_id
        order by extracted_at desc, loaded_at desc
    ) = 1

)

select * from deduplicated
