import ee


AOI_OPTIONS = {
    "MahaKanadarawa Water Influence Zone": "projects/rice-mapping-472904/assets/mk_influence_zone",
    "MahaKanadarawa Irrigable Area": "projects/rice-mapping-472904/assets/mk_Irrigable_Area"
}

ASSETS = {
    "points": "projects/rice-mapping-472904/assets/SamplePtsMahaKanadarawa",
    "roads": "projects/rice-mapping-472904/assets/mkRoads",
    "water": "projects/rice-mapping-472904/assets/mkTanks",
}

def load_assets():
    return {
        # AOIs
        "WIZ": ee.FeatureCollection(AOI_OPTIONS["MahaKanadarawa Water Influence Zone"]),
        "IA": ee.FeatureCollection(AOI_OPTIONS["MahaKanadarawa Irrigable Area"]),

        # Supporting layers
        "points": ee.FeatureCollection(ASSETS["points"]),
        "roads": ee.FeatureCollection(ASSETS["roads"]),
        "water": ee.FeatureCollection(ASSETS["water"])
    }