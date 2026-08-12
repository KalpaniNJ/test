# Placeholder for gee_helpers.py
import ee
import geemap
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.config import load_assets


def _build_mosaic_collection(aoi, start_date, end_date):
    """
    Builds the dekadal mRVI mosaic collection for an AOI/date range.

    Shared by get_time_series() and get_mosaic_collection() so this (expensive)
    Sentinel-1 speckle-filtering + mosaicking pipeline is defined in one place.
    Callers should go through the session-state cache in get_time_series() /
    get_mosaic_collection() rather than calling this directly, so the same
    AOI+date-range combo isn't rebuilt from scratch on every workflow step.
    """
    startDate = ee.Date(str(start_date))
    endDate = ee.Date(str(end_date))

    # Creates a list of dekads (12-day periods per month) from the given date range
    # Calculates the number of months between startDate and endDate
    # Creates a list of months starting from startDate
    numMonths = endDate.difference(startDate, 'month').round()

    def func_ocb(month):
        return startDate.advance(ee.Number(month), 'month')

    monthSequence = ee.List.sequence(0, numMonths, 1).map(func_ocb)

    # Function to generate dekad dates for a given month

    def func_jha(date):
        date = ee.Date(date)
        y = date.get('year')
        m = date.get('month')

        dekad1 = ee.Date.fromYMD(y, m, 1)
        dekad2 = ee.Date.fromYMD(y, m, 13)
        dekad3 = ee.Date.fromYMD(y, m, 25)

        return [dekad1, dekad2, dekad3]

    generateDekads = func_jha

    # Get the dekadList
    dekadList = monthSequence.map(generateDekads).flatten()

    def func_kbb(date):
        return ee.Algorithms.If(
        ee.Date(date).millis().lte(endDate.millis()),
        date,
        None
        )

    filteredDekadList = dekadList.map(func_kbb).removeAll([None])

    # Remove duplicate dekad dates from filteredDekadList
    filteredDekadList = filteredDekadList.distinct()

    # Define the Lee filter function for GEE
    def lee_filter_gee(img, n=2, ENL=5.0):
        """
        Lee Filter for speckle reduction in GEE.
        """
        img = ee.Image(img)
        kernel = ee.Kernel.square(radius=n, units='pixels', normalize=True)

        # Local mean and variance
        mean_img = img.reduceNeighborhood(reducer=ee.Reducer.mean(), kernel=kernel)
        var_img = img.reduceNeighborhood(reducer=ee.Reducer.variance(), kernel=kernel)

        sigma_v = ee.Number(1.0).divide(ENL).sqrt()  # (1/ENL)^0.5
        sigma_v2 = sigma_v.pow(2)

        var_x = var_img.subtract(mean_img.pow(2).multiply(sigma_v2)) \
                    .divide(ee.Number(1).add(sigma_v2))
        k = var_x.divide(var_img)
        k = k.where(k.lt(0), 0)

        lee_img = mean_img.add(k.multiply(img.subtract(mean_img)))

        # Explicitly ensure output is an ee.Image
        return ee.Image(lee_img).copyProperties(img, img.propertyNames())

    # Define polarization
    polarization = 'VH'

    # Small buffer beyond the AOI so the Lee filter's 5x5 neighborhood kernel
    # has valid neighbors right up to the AOI edge.
    aoi_buffered = aoi.buffer(100)

    # Load the Sentinel-1 GRD ImageCollection with raw SAR images (VV, VH)
    # and clip to the AOI immediately. Sentinel-1 scenes cover ~100x100km;
    # without clipping, the Lee filter below (a per-pixel neighborhood
    # convolution) runs over the entire scene footprint instead of just the
    # AOI, which is normally orders of magnitude smaller — this is the
    # single biggest cost in this pipeline.
    #
    # Fetch 12 extra days past endDate (matching the last dekad's window
    # below): endDate is an exclusive upper bound, and Sentinel-1's revisit
    # cycle is 6-12 days, so the last dekad (which spans [lastDekadStart,
    # lastDekadStart+12d) and can start exactly on endDate when endDate
    # lands on a dekad boundary) would otherwise have zero source images to
    # reduce even though real acquisitions exist just after endDate.
    # filteredDekadList still stops considering new dekads at endDate, so
    # this only extends the source pool, not which dekads get computed.
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT') \
        .filterBounds(aoi) \
        .filterDate(startDate, endDate.advance(12, 'day')) \
        .filter(ee.Filter.eq('instrumentMode','IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization)) \
        .filter(ee.Filter.eq('resolution_meters', 10)) \
        .map(lambda img: img.clip(aoi_buffered))

    # Apply Lee filter to raw bands
    def filter_raw(img):
        img = ee.Image(img)
        vv_f = ee.Image(lee_filter_gee(img.select('VV'), n=2, ENL=4.0)).rename('VV_filtered')
        vh_f = ee.Image(lee_filter_gee(img.select('VH'), n=2, ENL=4.0)).rename('VH_filtered')
        return img.addBands([vv_f, vh_f])

    s1_filtered = s1.map(filter_raw)

    # Calculate mRVI from filtered bands
    def add_mrvi(img):
        vv = img.select('VV_filtered')
        vh = img.select('VH_filtered')
        mRVI = vv.divide(vv.add(vh)).pow(0.5).multiply(vh.multiply(4).divide(vv.add(vh))).rename('mRVI')
        return img.addBands(mRVI)

    rvi_filtered = s1_filtered.map(add_mrvi).select('mRVI')
    rvi_sorted = rvi_filtered.sort("system:time_start")

    def func_wxd(dekad):
        start_date = ee.Date(dekad)
        currentIndex = ee.Number(filteredDekadList.indexOf(dekad))
        nextIndex = currentIndex.add(1)
        # For the last dekad, use a full 12-day window from its start date
        # rather than capping at endDate. Two problems with capping at
        # endDate: (1) whenever endDate lands exactly on a dekad boundary
        # (common, since season dates are snapped to dekads), start_date
        # equals endDate and filterDate(start_date, endDate) becomes a
        # zero-length range that Earth Engine hard-errors on ("Empty date
        # ranges not supported"); (2) even a same-day-plus-one window is far
        # narrower than Sentinel-1's revisit cycle (6-12 days), so it very
        # often catches zero images and silently drops the last dekad
        # instead of computing one. A fixed 12-day window matches the
        # spacing already used between other dekads (day1->day13->day25),
        # giving the last, possibly-partial dekad the same chance of
        # catching a pass as every other one.
        nextDate = ee.Algorithms.If(
            nextIndex.lt(filteredDekadList.size()),
            ee.Date(filteredDekadList.get(nextIndex)),
            start_date.advance(12, 'day')
        )

        dekadImages = rvi_sorted.filterDate(start_date, nextDate)
        mRVIImages = dekadImages.select('mRVI')

        def make_image():
            img = mRVIImages.reduce(ee.Reducer.median())
            # Set dekad and system:time_start correctly
            return img.set({
                'dekad': dekad,
                'system:time_start': start_date.millis()
            })

        return ee.Algorithms.If(
            mRVIImages.size().gt(0),
            make_image(),
            None
        )

    createMosaic = func_wxd

    # Convert List to ImageCollection & Remove Nulls
    mosaicImages = ee.List(filteredDekadList.map(createMosaic)).removeAll([None])
    mosaicCollection = ee.ImageCollection.fromImages(mosaicImages)

    def func_zty(img):
        # preserve properties
        img2 = img.multiply(10000).toUint16()
        return img2.copyProperties(img, ['dekad', 'system:time_start'])

    mosaicCollectionUInt16 = mosaicCollection.map(func_zty)

    return mosaicCollectionUInt16, filteredDekadList


def _get_cached_mosaic(aoi, start_date, end_date, aoi_name=None):
    """
    Returns (mosaicCollectionUInt16, filteredDekadList) for this AOI/date
    range, reusing a session-cached build when the Time Series and Rice
    Mapping steps are run back-to-back with the same AOI/dates (the normal
    workflow) instead of recomputing the whole Sentinel-1 speckle-filtering
    pipeline a second time.
    """
    cache_key = (aoi_name, str(start_date), str(end_date))
    if st.session_state.get("_mosaic_cache_key") == cache_key:
        return st.session_state["_mosaic_cache"], st.session_state["_mosaic_cache_dekads"]

    mosaicCollectionUInt16, filteredDekadList = _build_mosaic_collection(aoi, start_date, end_date)
    st.session_state["_mosaic_cache_key"] = cache_key
    st.session_state["_mosaic_cache"] = mosaicCollectionUInt16
    st.session_state["_mosaic_cache_dekads"] = filteredDekadList
    return mosaicCollectionUInt16, filteredDekadList


def get_time_series(aoi, start_date, end_date, aoi_name=None):
    assets = load_assets()
    points = assets["points"]

    mosaicCollectionUInt16, _ = _get_cached_mosaic(aoi, start_date, end_date, aoi_name)

    # Single sampling pass over the mosaic collection. Previously this ran
    # twice — once through a sequential `.iterate()` (a slow, non-parallel
    # GEE anti-pattern) to build df_line, and again through `.map().flatten()`
    # for df_points — even though both produced the same values. df_line and
    # df_points are now both derived from one getInfo() call.
    def sample_image_points(image):
        return image.sampleRegions(collection=points, scale=10, geometries=False) \
            .map(lambda f: f.set('time', image.date().format('YYYY-MM-dd')))

    sampled_fc = mosaicCollectionUInt16.map(sample_image_points).flatten()
    info = sampled_fc.getInfo()

    rows = [{
        "time": f["properties"].get("time"),
        "mRVI_median": f["properties"].get("mRVI_median"),
        # "system:index" is exposed as the feature's top-level "id" in the
        # GeoJSON response, not inside "properties" — reading it from
        # properties silently returns None for every row, which .dropna()
        # below would then wipe out entirely.
        "point_id": f.get("id")
    } for f in info["features"]]

    df_points = pd.DataFrame(rows).dropna()
    df_points["time"] = pd.to_datetime(df_points["time"])
    df_points = df_points.sort_values("time")

    df_line = df_points.rename(columns={"mRVI_median": "mRVI"}).copy()

    return df_line, df_points


def get_mosaic_collection(aoi, start_date, end_date, aoi_name=None):
    return _get_cached_mosaic(aoi, start_date, end_date, aoi_name)


def compute_statistics(aoi, maskedPaddyClassification, maskedStartMonth, maskedStartMonthDay):

    total_area = (
        maskedPaddyClassification.multiply(ee.Image.pixelArea())
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    total_area_ha = list(total_area.values())[0] / 10000  # convert m² → ha

    # --- Area by Month
    month_area = (
        ee.Image.pixelArea().addBands(maskedStartMonth)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='month'),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    month_stats = {g["month"]: g["sum"] / 10000 for g in month_area["groups"]}

    # --- Area by MMDD
    mmdd_area = (
        ee.Image.pixelArea().addBands(maskedStartMonthDay)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='mmdd'),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    mmdd_stats = {g["mmdd"]: g["sum"] / 10000 for g in mmdd_area["groups"]}

    return total_area_ha, month_stats, mmdd_stats


def get_sar_rgb(aoi, start_date, season_start, peak_date, harvest_date, orbit_pass="DESCENDING"):
    """
    Generate a Sentinel-1 VV RGB composite:
        R = mean VV between start and peak (pre-peak)
        G = mean VV between peak and harvest (peak to harvest)
        B = mean VV between harvest and one month after harvest (post-harvest)
    Args:
        aoi (ee.Geometry or ee.FeatureCollection): Area of interest.
        start_date (str): Start date (e.g., "2022-06-01").
        peak_date (str): Peak date (e.g., "2022-09-01").
        harvest_date (str): Harvest date (e.g., "2022-11-01").
        orbit_pass (str): Sentinel-1 orbit ("ASCENDING" or "DESCENDING").
    Returns:
        ee.Image: A 3-band RGB composite (VV polarization).
    """

    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("orbitProperties_pass", orbit_pass))
        .select(["VV"])
    )

    im1 = s1.filterDate(start_date, season_start).mean()
    im2 = s1.filterDate(season_start, peak_date).mean()
    im3 = s1.filterDate(peak_date, harvest_date).mean()

    sar_rgb = im1.addBands(im2).addBands(im3).clip(aoi)
    return sar_rgb.set({
        "description": f"S1_RGB_{start_date}_{harvest_date}",
        "orbit_pass": orbit_pass
    })
