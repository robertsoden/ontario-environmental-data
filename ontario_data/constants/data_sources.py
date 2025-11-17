"""URLs and endpoints for Ontario environmental data sources."""

# Biodiversity Data Sources
DATA_SOURCE_URLS = {
    # Biodiversity and Species
    "inaturalist_api": "https://api.inaturalist.org/v1",
    "inaturalist_web": "https://www.inaturalist.org",
    "ebird_api": "https://api.ebird.org/v2",
    "ebird_web": "https://ebird.org",
    "gbif_api": "https://api.gbif.org/v1",
    "gbif_web": "https://www.gbif.org",

    # Water Quality
    "datastream_api": "https://datastream.org/api",
    "datastream_web": "https://datastream.org",

    # Government Data
    "ontario_data_catalogue": "https://data.ontario.ca",
    "ontario_geohub": "https://geohub.lio.gov.on.ca",
    "open_canada": "https://open.canada.ca",

    # Forest and Land Cover
    "ontario_fri": "https://data.ontario.ca/dataset/forest-resources-inventory",
    "gfw_api": "https://data-api.globalforestwatch.org",

    # Indigenous Data
    "isc_water_advisories": "https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660",
    "stats_can_boundaries": "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index-eng.cfm",
}

# API Documentation URLs
API_DOCS = {
    "inaturalist": "https://api.inaturalist.org/v1/docs/",
    "ebird": "https://documenter.getpostman.com/view/664302/S1ENwy59",
    "gbif": "https://www.gbif.org/developer/summary",
    "datastream": "https://docs.datastream.org/",
}

# API Key Registration
API_KEY_REGISTRATION = {
    "ebird": "https://ebird.org/api/keygen",
    "gbif": "https://www.gbif.org/user/download",
}
