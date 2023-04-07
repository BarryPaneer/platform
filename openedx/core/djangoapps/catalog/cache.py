# Template used to create cache keys for individual programs.
PROGRAM_CACHE_KEY_TPL = 'program-{uuid}'

# Cache key used to locate an item containing a list of all program UUIDs for a site.
SITE_PROGRAM_UUIDS_CACHE_KEY_TPL = 'program-uuids-{domain}'

# Site-aware cache key template used to locate an item containing
# a list of all program UUIDs with a certain program type (the Site is required
# because program_type values are likely to be shared between different sites
# that live in the same environment).
PROGRAMS_BY_TYPE_CACHE_KEY_TPL = 'programs-by-type-{site_id}-{program_type}'
