import ee


AOI_OPTIONS = {
    # "MahaKanadarawa Water Influence Zone": "projects/rice-mapping-472904/assets/mk_influence_zone",
    # "MahaKanadarawa Irrigable Area": "projects/rice-mapping-472904/assets/mk_Irrigable_Area"
    "Walawa Irrigation Scheme": "projects/ricemapping-475407/assets/UWIS_aoi"
}

ASSETS = {
    "points": "projects/ricemapping-475407/assets/UWIS_pts",
    "roads": "projects/ricemapping-475407/assets/UWIS_roads",
    "water": "projects/ricemapping-475407/assets/UWIS_water",
}

def load_assets():
    return {
        # AOIs
        "WIS": ee.FeatureCollection(AOI_OPTIONS["Walawa Irrigation Scheme"])
        # "IA": ee.FeatureCollection(AOI_OPTIONS["MahaKanadarawa Irrigable Area"]),

        # Supporting layers
        "points": ee.FeatureCollection(ASSETS["points"]),
        "roads": ee.FeatureCollection(ASSETS["roads"]),
        "water": ee.FeatureCollection(ASSETS["water"])
    }
